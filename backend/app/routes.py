from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, status
from fastapi.responses import JSONResponse
from firebase_admin import auth, db, storage
import random
from models import Restaurant, MenuItem, MenuItemUpdate, BulkMenuUpdate
from typing import List, Optional
from auth_routes import verify_token
from permissions import can_manage_restaurant, can_edit_menu, is_restaurant_owner
import os
import json
from pydantic import BaseModel
from google.generativeai.types import RequestOptions
from google.api_core import retry
import asyncio
import concurrent.futures
from uuid import uuid4
from datetime import timedelta

try:
    import google.generativeai as genai
except Exception:
    genai = None

router = APIRouter()

MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB


def generate_id(ref_path: str, length: int = 5, max_attempts: int = 5) -> str:
    """
    Generate a unique numeric ID and verify it doesn't exist in the database.

    Args:
        ref_path: Firebase reference path to check for existing IDs
        length: Length of the ID to generate
        max_attempts: Maximum number of attempts to generate a unique ID

    Returns:
        str: A unique numeric ID

    Raises:
        HTTPException: If unable to generate a unique ID after max_attempts
    """
    ref = db.reference(ref_path)

    for _ in range(max_attempts):
        # Generate a number with exact length (e.g., 10000 to 99999 for length=5)
        min_value = 10 ** (length - 1)
        max_value = (10**length) - 1
        new_id = str(random.randint(min_value, max_value))

        # Check if ID exists in database
        if not ref.child(new_id).get():
            return new_id

    raise HTTPException(
        status_code=500,
        detail=f"Unable to generate unique ID after {max_attempts} attempts",
    )


# Best-effort classification of upstream timeout errors from various libraries
def _is_timeout_error(error: Exception) -> bool:
    try:
        from google.api_core.exceptions import DeadlineExceeded, RetryError  # type: ignore
    except Exception:
        DeadlineExceeded = tuple()  # type: ignore
        RetryError = tuple()  # type: ignore

    timeout_types = (
        asyncio.TimeoutError,
        TimeoutError,  # builtin
        concurrent.futures.TimeoutError,
    )
    if isinstance(error, timeout_types):
        return True
    # Google API Core timeouts
    if isinstance(error, (DeadlineExceeded, RetryError)):  # type: ignore
        return True
    # Fallback: string heuristics
    text = str(error).lower()
    return any(token in text for token in ("deadline exceeded", "timeout", "timed out"))


VALID_ALLERGENS = {
    "milk",
    "eggs",
    "fish",
    "tree_nuts",
    "wheat",
    "shellfish",
    "gluten_free",
    "peanuts",
    "soybeans",
    "sesame",
}

VALID_DIETARY_CATEGORIES = {"vegan", "vegetarian"}


async def _get_authenticated_user(token_data: dict):
    user_id = token_data.get("uid")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user token")

    try:
        user_record = auth.get_user(user_id)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid user token")

    return user_id, user_record


async def _authorize_restaurant_access(restaurant_id: str, token_data: dict):
    user_id, user_record = await _get_authenticated_user(token_data)
    is_admin = await check_admin_status(token_data)

    restaurant_ref = db.reference(f"restaurants/{restaurant_id}")
    restaurant_data = restaurant_ref.get()
    if not restaurant_data:
        raise HTTPException(status_code=404, detail=f"Restaurant {restaurant_id} not found")

    if restaurant_data.get("owner_uid") != user_id and not is_admin:
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to modify this restaurant's menu",
        )

    return restaurant_data, user_record, is_admin


def _normalize_menu_item_record(item_id: str, item_data: dict, restaurant_id: str):
    normalized = {"id": str(item_id), **(item_data or {})}
    normalized["restaurant_id"] = restaurant_id
    normalized["archived"] = bool(normalized.get("archived", False))
    normalized.setdefault("ingredients", "")
    normalized.setdefault("allergens", [])
    normalized.setdefault("dietaryCategories", [])
    return normalized


def _merge_tag_updates(existing_values: List[str], additions: List[str], removals: List[str]) -> List[str]:
    merged = [value for value in (existing_values or []) if value not in removals]
    for value in additions or []:
        if value not in merged:
            merged.append(value)
    return merged


# Check if the user is an admin
async def check_admin_status(token_data: dict) -> bool:
    """Check if the user has admin privileges based on token data"""
    user_id = token_data.get("uid")
    if not user_id:
        return False

    # Get user data from database to check admin status
    user_ref = db.reference(f"users/{user_id}")
    user_data = user_ref.get()

    # Return admin status
    return user_data.get("is_admin", False) if user_data else False


class ParseIngredientsRequest(BaseModel):
    ingredients: str


@router.post("/ai/parse-ingredients")
async def parse_ingredients_ai(
    payload: ParseIngredientsRequest, token_data: dict = Depends(verify_token)
):
    try:
        user_id = token_data.get("uid")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user token")

        api_key = os.getenv("GOOGLE_AI_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_AI_API_KEY env var is not set on the server",
            )

        if genai is None:
            raise HTTPException(
                status_code=500,
                detail="google-generativeai library is not installed on the server",
            )

        genai.configure(api_key=api_key)

        # Determine candidate models: prefer env override, then SDK-discovered, then fallbacks
        env_model = os.getenv("GEMINI_MODEL")
        candidate_models: List[str] = []
        if env_model:
            candidate_models.append(env_model)

        # Try to discover models supported for generateContent via SDK
        try:
            discovered = [
                m.name
                for m in genai.list_models()
                if getattr(m, "supported_generation_methods", None)
                and "generateContent" in m.supported_generation_methods
            ]
            # Simple preference ordering: flash/pro, 1.5 > 1.0 > others
            preference = ["1.5", "flash", "pro"]
            discovered_sorted = sorted(
                discovered,
                key=lambda n: (0 if any(p in n for p in preference) else 1, n),
            )
            for n in discovered_sorted:
                if n not in candidate_models:
                    candidate_models.append(n)
        except Exception:
            pass

        # Final fallbacks in case discovery failed
        for fb in [
            "gemini-1.5-flash-001",
            "gemini-1.5-flash",
            "gemini-1.5-flash-latest",
            "gemini-1.5-flash-002",
            "gemini-1.5-pro",
            "gemini-1.0-pro",
            "gemini-pro",
        ]:
            if fb not in candidate_models:
                candidate_models.append(fb)

        prompt = (
            "You are extracting food safety attributes from free-text ingredient lists.\n"
            "Given the text, return a strict JSON object with keys: allergens (array of strings), "
            "dietaryCategories (array of strings), and extractedIngredients (array of strings).\n"
            "The allowed allergen ids are: milk, eggs, fish, tree_nuts, wheat, shellfish, peanuts, soybeans, sesame.\n"
            "The allowed dietary category ids are: vegan, vegetarian.\n"
            "Normalize synonyms to these ids (e.g., 'tree nuts' -> 'tree_nuts').\n"
            "Only output valid ids. If none, output empty arrays.\n"
            f"Text: {payload.ingredients}"
        )

        last_error = None
        response = None
        for model_name in candidate_models:
            try:
                model = genai.GenerativeModel(
                    model_name=model_name,
                    generation_config={
                        "temperature": 0,
                        "response_mime_type": "application/json",
                    },
                )
                try:
                    response = model.generate_content(prompt)
                except Exception as e:
                    if _is_timeout_error(e):
                        return JSONResponse(status_code=504, content={"error": "upstream_timeout"})
                    raise
                if response and getattr(response, "text", None):
                    break
            except Exception as e:
                last_error = e
                continue

        if response is None or not getattr(response, "text", None):
            err_msg = "Model not available or failed to generate. "
            if last_error:
                err_msg += str(last_error)
            raise HTTPException(status_code=500, detail=err_msg)
        raw_text = response.text

        try:
            parsed = json.loads(raw_text)
        except Exception:
            # Fallback: try to locate a JSON object in the text
            start = raw_text.find("{")
            end = raw_text.rfind("}")
            if start != -1 and end != -1 and end > start:
                parsed = json.loads(raw_text[start : end + 1])
            else:
                raise

        # Post-process and validate IDs against backend sets
        valid_allergens = {
            "milk",
            "eggs",
            "fish",
            "tree_nuts",
            "wheat",
            "shellfish",
            "peanuts",
            "soybeans",
            "sesame",
        }
        valid_dietary = {"vegan", "vegetarian"}

        # Accept some common synonyms and map to our ids
        allergen_synonyms = {
            "tree nuts": "tree_nuts",
            "treenuts": "tree_nuts",
            "gluten": "wheat",  # approximate mapping for common usage
        }

        def normalize_id(value: str) -> str:
            v = (value or "").strip().lower()
            if v in allergen_synonyms:
                v = allergen_synonyms[v]
            v = v.replace(" ", "_")
            return v

        allergens = [normalize_id(a) for a in parsed.get("allergens", [])]
        allergens = [a for a in allergens if a in valid_allergens]

        dietary = [normalize_id(c) for c in parsed.get("dietaryCategories", [])]
        dietary = [d for d in dietary if d in valid_dietary]

        extracted_ingredients = parsed.get("extractedIngredients", []) or []

        return {
            "allergens": allergens,
            "dietaryCategories": dietary,
            "extractedIngredients": extracted_ingredients,
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"AI parse error: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to parse ingredients with AI"
        )


def _ensure_genai_configured() -> None:
    api_key = os.getenv("GOOGLE_AI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_AI_API_KEY env var is not set on the server",
        )
    if genai is None:
        raise HTTPException(
            status_code=500,
            detail="google-generativeai library is not installed on the server",
        )
    genai.configure(api_key=api_key)


def _select_model_name(purpose: Optional[str] = None) -> str:
    """
    Select a model name for a given purpose.

    Priority:
    - GEMINI_INGEST_MODEL for ingestion
    - GEMINI_PARSE_MODEL for parsing
    - GEMINI_MODEL as a global override
    - Otherwise, auto-discover from list_models().
    """
    env_model = None
    if purpose == "ingest":
        env_model = os.getenv("GEMINI_INGEST_MODEL")
    elif purpose == "parse":
        env_model = os.getenv("GEMINI_PARSE_MODEL")

    if not env_model:
        env_model = os.getenv("GEMINI_MODEL")

    if env_model:
        return env_model

    try:
        discovered = [
            m.name
            for m in genai.list_models()
            if getattr(m, "supported_generation_methods", None)
            and "generateContent" in m.supported_generation_methods
        ]
        # Simple preference ordering: prefer flash/2.x/3.x models
        preference = ["3", "2.5", "2.0", "flash", "pro"]
        discovered_sorted = sorted(
            discovered,
            key=lambda n: (0 if any(p in n for p in preference) else 1, n),
        )
        if discovered_sorted:
            return discovered_sorted[0]
    except Exception:
        pass

    # Final static fallbacks (older model names, may or may not exist)
    for fb in [
        "gemini-flash-latest",
        "gemini-pro-latest",
    ]:
        return fb


@router.post("/ai/ingest-menu")
async def ingest_menu_file(  # 1. Renamed for clarity
    file: UploadFile = File(...), token_data: dict = Depends(verify_token)
):
    try:
        user_id = token_data.get("uid")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user token")

        # 2. Add "application/pdf" to supported types
        supported_mime_types = (
            "image/png",
            "image/jpeg",
            "image/jpg",
            "application/pdf",
        )
        if file.content_type not in supported_mime_types:
            raise HTTPException(
                status_code=400,
                # 3. Update error message
                detail="Only PNG/JPEG images and PDFs are supported.",
            )

        _ensure_genai_configured()

        # Use a potentially heavier, multimodal-capable model for ingestion.
        model_name = _select_model_name("ingest")
        model = genai.GenerativeModel(
            model_name=model_name,
            generation_config={
                "temperature": 0,
                "response_mime_type": "application/json",
            },
        )

        file_bytes = await file.read()

        # Persist the original uploaded menu file to Cloud Storage for auditing/debugging.
        try:
            bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET")
            bucket = storage.bucket(bucket_name) if bucket_name else storage.bucket()

            original_name = file.filename or "menu"
            _, ext = os.path.splitext(original_name)
            ext = ext.lower() if ext else ""
            source_key = f"menu_files/{user_id}/{uuid4().hex}{ext}"

            source_blob = bucket.blob(source_key)
            source_blob.upload_from_string(file_bytes, content_type=file.content_type)
        except Exception as storage_error:
            # Log but do not fail the ingestion if archival storage is unavailable.
            print(f"Error archiving menu file to storage: {storage_error}")

        # 5. This logic now works for images AND PDFs seamlessly
        model_part = {
            "mime_type": file.content_type,
            "data": file_bytes,
        }

        # 6. Update prompt to be file-generic
        prompt = (
            "You are a high-accuracy menu extraction bot. Your sole task is to extract menu items "
            "from the document and return ONLY a single, strict JSON object.\n"
            "Do not include any preamble, explanations, or any text other than the JSON object.\n\n"
            "The JSON object must have a single key 'items', which is an array of item objects.\n"
            "Each item object must have this exact structure:\n"
            "{\n"
            "  'name': 'string', (The concise, primary name of the item)\n"
            "  'description': 'string', (The description text, or '' if none)\n"
            "  'price': number, (Numeric value only, e.g., 14.50. No currency symbols, no ranges.)\n"
            "  'ingredients': [array of strings] (A list of all ingredient strings)\n"
            "}\n\n"
            "---"
            "### **CRITICAL INSTRUCTIONS for 'ingredients' field**\n"
            "You must build the ingredients list by following these steps IN ORDER:\n\n"
            "1.  **Start with the Name:** ALWAYS add the main food component(s) from the item's 'name' as the first ingredient(s).\n"
            "    * **Example:** If 'name' is 'Rigatoni', the 'ingredients' array **must** include 'rigatoni'.\n"
            "    * **Example:** If 'name' is 'Chicken Sandwich', the 'ingredients' array **must** include 'chicken' and 'bread'.\n"
            "    * **Example:** If 'name' is 'Mushroom Pizza', the 'ingredients' array **must** include 'mushroom' and 'pizza dough'.\n\n"
            "2.  **Add from Description:** After adding from the name, scan the 'description' and add ALL other ingredients explicitly mentioned.\n"
            "    * **Example:** If 'description' is 'topped with parmesan and fresh basil', you must add 'parmesan' and 'fresh basil' to the array.\n\n"
            "3.  **Infer if Necessary:** If the description is empty, infer any other *absolutely essential* ingredients implied by the name that are not already listed.\n"
            "    * **Example:** For 'Latte', you would first add 'latte' (from the name), then infer and add 'espresso' and 'milk'.\n"
            "    * **Example:** For 'Queso Dip', you would first add 'queso' (from the name), then infer and add 'cheese'.\n\n"
            "4.  **Format:** The final output for 'ingredients' MUST be a JSON array of strings."
        )

        # 7. The AI call is identical, just using the generic 'model_part'
        try:
            # Use a single-call timeout rather than a long retry chain to keep UX snappy.
            response = model.generate_content(
                [prompt, model_part],
                request_options=RequestOptions(timeout=90),
            )
        except Exception as e:
            if _is_timeout_error(e):
                return JSONResponse(status_code=504, content={"error": "upstream_timeout"})
            raise
        raw_text = response.text or ""

        try:
            parsed = json.loads(raw_text)
        except Exception:
            start = raw_text.find("{")
            end = raw_text.rfind("}")
            if start != -1 and end != -1 and end > start:
                parsed = json.loads(raw_text[start : end + 1])
            else:
                raise

        items = parsed.get("items", [])
        if not isinstance(items, list):
            items = []

        # --- NO CHANGES NEEDED BELOW THIS LINE ---
        # This entire section processes the *text* extracted by the first
        # AI call, so it's completely independent of the original file type.

        normalized_items = []
        for item in items:
            name = (item.get("name") or "").strip()
            description = (item.get("description") or "").strip()
            # price: try to coerce to float
            price_value = item.get("price")
            try:
                price = float(price_value)
            except Exception:
                # Try to scrub non-digits
                try:
                    price = float(str(price_value).replace("$", "").strip())
                except Exception:
                    price = 0.0

            # Get the list of ingredients from the AI's output
            ingredients_list = item.get("ingredients", []) or []

            # Join the list of strings into a single comma-separated string
            if isinstance(ingredients_list, list):
                ingredients_text = ", ".join(ingredients_list)
            else:
                # Add a fallback in case the AI returned a single string by mistake
                ingredients_text = str(ingredients_list).strip()

            # Reuse the same parsing pipeline by calling the model once more for ingredients
            ai_parse_request = ParseIngredientsRequest(ingredients=ingredients_text)
            # Inline invocation of the same logic as parse_ingredients_ai
            # Configure and select model
            _ensure_genai_configured()
            # Use a lighter, cheaper model for per-item parsing/classification.
            model_name_local = _select_model_name("parse")
            model_local = genai.GenerativeModel(
                model_name=model_name_local,
                generation_config={
                    "temperature": 0,
                    "response_mime_type": "application/json",
                },
            )
            ing_prompt = (
                "You are an expert food safety and dietary attribute extractor. Your task is to analyze a free-text ingredient list and return a single, strict JSON object.\n"
                "Do not provide any preamble, explanation, or any text other than the JSON object itself.\n\n"
                "### JSON Structure:\n"
                "{\n"
                '  "allergens": [array of strings],\n'
                '  "dietaryCategories": [array of strings],\n'
                '  "extractedIngredients": [array of strings] (List all distinct ingredients found in the text)\n'
                "}\n\n"
                "---"
                "### Allowed IDs:\n"
                "* **Allergens:** `milk`, `eggs`, `fish`, `tree_nuts`, `wheat`, `shellfish`, `peanuts`, `soybeans`, `sesame`\n"
                "* **Dietary Categories:** `vegan`, `vegetarian`\n\n"
                "---"
                "### **CRITICAL EXTRACTION RULES**\n\n"
                "**1. Dietary Category Rules (Follow Strictly):**\n\n"
                "* **For `vegetarian`:**\n"
                "    * **DO NOT** assign `vegetarian` if *any* meat, poultry, fish, or shellfish products are present.\n"
                "    * **Exclusion list (check carefully):** `anchovies`, `prosciutto`, `bacon`, `ham`, `chicken`, `beef`, `pork`, `fish`, `shrimp`, `crab`, `lobster`, `gelatin`, `chicken broth`, `beef stock`, `fish sauce`, `lard`.\n\n"
                "* **For `vegan`:**\n"
                "    * **DO NOT** assign `vegan` if *any* animal-derived products are present.\n"
                "    * This includes all items on the `vegetarian` exclusion list, **PLUS:** `milk`, `cheese`, `butter`, `cream`, `yogurt`, `eggs`, `honey`, `whey`, `casein`, `collagen`.\n"
                '    * If an item qualifies as `vegan`, it *also* qualifies as `vegetarian`. In this case, the output array must be `["vegan", "vegetarian"]`.\n\n'
                "**2. Allergen Rules (Follow Strictly):**\n\n"
                "* **`wheat` (Inference Rule):**\n"
                "    * **YOU MUST** assume `wheat` is present if the ingredients list `pasta`, `flour`, `bread`, `semolina`, `couscous`, `farro`, `spelt`, or `noodles`.\n"
                "    * **Exception:** Do *not* assign `wheat` only if the item is explicitly qualified as non-wheat (e.g., `gluten-free pasta`, `rice flour`, `almond flour`, `rice noodles`).\n\n"
                "* **`fish`:**\n"
                "    * Must be included for all types of fish, including `anchovies`.\n\n"
                "* **`milk`:**\n"
                "    * Must be included for `milk` and all common dairy products like `cheese`, `butter`, `yogurt`, `cream`, `whey`, `casein`.\n\n"
                "**3. General Rules:**\n"
                "* Normalize all synonyms to the allowed IDs (e.g., 'soya' -> 'soybeans', 'pecans' -> 'tree_nuts', 'parmesan' -> 'milk').\n"
                "* If no attributes for a category are found, output an empty array `[]` for that key.\n\n"
                "---"
                f"Text to analyze: {ai_parse_request.ingredients}"
            )
            try:
                ai_resp = model_local.generate_content(
                    ing_prompt,
                    request_options=RequestOptions(timeout=30),
                )
            except Exception as e:
                if _is_timeout_error(e):
                    return JSONResponse(status_code=504, content={"error": "upstream_timeout"})
                raise
            ai_raw = ai_resp.text or "{}"
            try:
                ai_parsed = json.loads(ai_raw)
            except Exception:
                s = ai_raw.find("{")
                e = ai_raw.rfind("}")
                ai_parsed = (
                    json.loads(ai_raw[s : e + 1])
                    if s != -1 and e != -1 and e > s
                    else {}
                )

            # Validate ids
            valid_allergens = {
                "milk",
                "eggs",
                "fish",
                "tree_nuts",
                "wheat",
                "shellfish",
                "peanuts",
                "soybeans",
                "sesame",
            }
            valid_dietary = {"vegan", "vegetarian"}
            synonyms = {
                "tree nuts": "tree_nuts",
                "treenuts": "tree_nuts",
                "gluten": "wheat",
            }

            def norm(v: str) -> str:
                t = (v or "").strip().lower()
                if t in synonyms:
                    t = synonyms[t]
                return t.replace(" ", "_")

            allergens = [
                a
                for a in [norm(x) for x in ai_parsed.get("allergens", [])]
                if a in valid_allergens
            ]
            dietary = [
                d
                for d in [norm(x) for x in ai_parsed.get("dietaryCategories", [])]
                if d in valid_dietary
            ]
            extracted_ingredients = ai_parsed.get("extractedIngredients", []) or []
            if extracted_ingredients and not ingredients_text:
                ingredients_text = ", ".join(extracted_ingredients)

            normalized_items.append(
                {
                    "name": name,
                    "description": description,
                    "price": price,
                    "ingredients": ingredients_text,
                    "allergens": allergens,
                    "dietaryCategories": dietary,
                }
            )

        return {"items": normalized_items}
    except HTTPException:
        raise
    except Exception as e:
        # 8. Update log/error messages
        print(f"Ingest file error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to ingest menu file")


@router.post("/restaurants/")
async def create_restaurant(
    restaurant: Restaurant, token_data: dict = Depends(verify_token)
):
    try:
        # Extract user ID from token
        user_id = token_data.get("uid")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user token")

        restaurant_id = generate_id("restaurants")
        restaurant_dict = restaurant.dict()

        # Add owner_uid to the restaurant data
        restaurant_dict["owner_uid"] = user_id

        ref = db.reference("restaurants")
        print(f"Attempting to create restaurant: {restaurant_dict}")

        ref.child(restaurant_id).set(restaurant_dict)
        print(f"Successfully created restaurant with ID: {restaurant_id}")

        # Add creator as manager in restaurant_members
        members_ref = db.reference(f"restaurant_members/{restaurant_id}")
        members_ref.set({user_id: {"role": "manager"}})

        # Check if this is the user's first restaurant and update user data
        user_ref = db.reference(f"users/{user_id}")
        user_data = user_ref.get()

        if user_data and not user_data.get("restaurant_id"):
            user_ref.update({"restaurant_id": restaurant_id})

        return {"id": restaurant_id, **restaurant_dict}
    except Exception as e:
        print(f"Error creating restaurant: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/restaurants")
async def get_restaurants(token_data: dict = Depends(verify_token)):
    try:
        # Extract user ID from token
        user_id = token_data.get("uid")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user token")

        # Check if user is admin
        is_admin = await check_admin_status(token_data)

        # Get restaurants
        ref = db.reference("restaurants")
        all_restaurants = ref.get()

        if not all_restaurants:
            return []

        # Admins see all; others see restaurants where they are owner or in restaurant_members
        members_by_restaurant = db.reference("restaurant_members").get() or {}
        if is_admin:
            restaurants = [
                {"id": str(rid), **rdata}
                for rid, rdata in all_restaurants.items()
            ]
        else:
            restaurants = [
                {"id": str(rid), **rdata}
                for rid, rdata in all_restaurants.items()
                if rdata.get("owner_uid") == user_id or (rid in members_by_restaurant and user_id in members_by_restaurant.get(rid, {}))
            ]

        return restaurants
    except Exception as e:
        print(f"Error fetching restaurants: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/restaurants/{restaurant_id}")
async def get_restaurant(restaurant_id: str, token_data: dict = Depends(verify_token)):
    try:
        # Extract user ID from token
        user_id = token_data.get("uid")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user token")

        # Check if user is admin
        is_admin = await check_admin_status(token_data)

        # Get the restaurant
        ref = db.reference(f"restaurants/{restaurant_id}")
        restaurant_data = ref.get()

        if not restaurant_data:
            raise HTTPException(
                status_code=404, detail=f"Restaurant {restaurant_id} not found"
            )

        # Verify access: manager, staff, or admin (any role can view)
        if not can_edit_menu(db, user_id, restaurant_id, is_admin):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to access this restaurant",
            )

        return {"id": restaurant_id, **restaurant_data}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching restaurant: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/restaurants/{restaurant_id}")
async def update_restaurant(
    restaurant_id: str, restaurant: Restaurant, token_data: dict = Depends(verify_token)
):
    """
    Update basic restaurant information (name, address, phone, cuisine_type).
    Only the owner of the restaurant or an admin can perform this action.
    """
    try:
        # Extract user ID from token
        user_id = token_data.get("uid")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user token")

        # Check if user is admin
        is_admin = await check_admin_status(token_data)

        # Load existing restaurant
        ref = db.reference(f"restaurants/{restaurant_id}")
        restaurant_data = ref.get()

        if not restaurant_data:
            raise HTTPException(
                status_code=404, detail=f"Restaurant {restaurant_id} not found"
            )

        # Only manager (or admin) can update restaurant
        if not can_manage_restaurant(db, user_id, restaurant_id, is_admin):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to modify this restaurant",
            )

        # Update allowed fields while preserving owner_uid and any other metadata
        updated_fields = restaurant.dict()
        restaurant_data.update(updated_fields)

        ref.set(restaurant_data)

        return {"id": restaurant_id, **restaurant_data}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating restaurant: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/restaurants/{restaurant_id}")
async def delete_restaurant(
    restaurant_id: str, token_data: dict = Depends(verify_token)
):
    """Remove a restaurant and its menu items and team data. Owner only (owner_uid)."""
    try:
        user_id = token_data.get("uid")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user token")

        restaurant_ref = db.reference(f"restaurants/{restaurant_id}")
        restaurant_data = restaurant_ref.get()

        if not restaurant_data:
            raise HTTPException(
                status_code=404, detail=f"Restaurant {restaurant_id} not found"
            )

        if not is_restaurant_owner(db, user_id, restaurant_id):
            raise HTTPException(
                status_code=403,
                detail="Only the restaurant owner can delete this restaurant",
            )

        menu_root = db.reference("menu_items")
        all_items = menu_root.get() or {}
        if isinstance(all_items, dict):
            for item_id, item_data in list(all_items.items()):
                if isinstance(item_data, dict) and item_data.get(
                    "restaurant_id"
                ) == restaurant_id:
                    db.reference(f"menu_items/{item_id}").delete()

        db.reference(f"restaurant_members/{restaurant_id}").delete()
        restaurant_ref.delete()

        user_ref = db.reference(f"users/{user_id}")
        user_data = user_ref.get() or {}
        if user_data.get("restaurant_id") == restaurant_id:
            user_ref.child("restaurant_id").delete()

        return {"message": f"Restaurant {restaurant_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting restaurant: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Menu item routes remain largely the same but now check for admin status too
@router.post("/restaurants/{restaurant_id}/menu")
async def add_menu_item(
    restaurant_id: str, menu_item: MenuItem, token_data: dict = Depends(verify_token)
):
    try:
        # Extract user ID from token
        user_id = token_data.get("uid")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user token")

        # Check if user is admin
        is_admin = await check_admin_status(token_data)

        # Verify restaurant exists
        restaurant_ref = db.reference(f"restaurants/{restaurant_id}")
        restaurant_data = restaurant_ref.get()

        if not restaurant_data:
            raise HTTPException(
                status_code=404, detail=f"Restaurant {restaurant_id} not found"
            )

        # Manager or staff (or admin) can add menu items
        if not can_edit_menu(db, user_id, restaurant_id, is_admin):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to modify this restaurant's menu",
            )

        # Validate allergens and dietary categories
        invalid_allergens = set(menu_item.allergens) - VALID_ALLERGENS
        if invalid_allergens:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid allergens: {', '.join(invalid_allergens)}",
            )

        invalid_categories = set(menu_item.dietaryCategories) - VALID_DIETARY_CATEGORIES
        if invalid_categories:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid dietary categories: {', '.join(invalid_categories)}",
            )

        menu_item_id = generate_id("menu_items")
        menu_item_dict = menu_item.dict()

        # Add restaurant_id and item_id to the menu item data
        menu_item_data = {
            **menu_item_dict,
            "restaurant_id": restaurant_id,
            "id": menu_item_id,
        }

        # Store menu item
        menu_ref = db.reference("menu_items")
        menu_ref.child(menu_item_id).set(menu_item_data)

        return menu_item_data

    except HTTPException as he:
        # Re-raise HTTP exceptions as is
        raise he
    except Exception as e:
        print(f"Error adding menu item: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/restaurants/{restaurant_id}/menu")
async def get_menu_items(
    restaurant_id: str,
    dietary_category: Optional[str] = None,
    allergen_free: Optional[List[str]] = None,
    token_data: dict = Depends(verify_token),
):
    try:
        # Extract user ID from token
        user_id = token_data.get("uid")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user token")

        # Check if user is admin
        is_admin = await check_admin_status(token_data)

        # Verify restaurant exists
        restaurant_ref = db.reference(f"restaurants/{restaurant_id}")
        restaurant_data = restaurant_ref.get()

        if not restaurant_data:
            raise HTTPException(
                status_code=404, detail=f"Restaurant {restaurant_id} not found"
            )

        # Manager or staff (or admin) can view menu
        if not can_edit_menu(db, user_id, restaurant_id, is_admin):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to access this restaurant's menu",
            )

        # Get all menu items for the restaurant
        menu_ref = db.reference("menu_items")
        menu_items = menu_ref.get()

        if not menu_items:
            return []

        # Filter menu items for this restaurant
        restaurant_menu = [
            _normalize_menu_item_record(item_id, item_data, restaurant_id)
            for item_id, item_data in menu_items.items()
            if item_data.get("restaurant_id") == restaurant_id
        ]

        # Attach short-lived signed image URLs for any items that have an image path.
        bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET")
        bucket = storage.bucket(bucket_name) if bucket_name else storage.bucket()

        for item in restaurant_menu:
            image_path = item.get("image_path")
            if image_path:
                try:
                    blob = bucket.blob(image_path)
                    signed_url = blob.generate_signed_url(
                        expiration=timedelta(hours=1),
                        method="GET",
                    )
                    item["image_url"] = signed_url
                except Exception as e:
                    # If generating a signed URL fails, log and continue without image_url
                    print(f"Error generating signed URL for {image_path}: {e}")

        # Apply dietary category filter if specified
        if dietary_category:
            restaurant_menu = [
                item
                for item in restaurant_menu
                if dietary_category in item.get("dietaryCategories", [])
            ]

        # Apply allergen-free filter if specified
        if allergen_free:
            restaurant_menu = [
                item
                for item in restaurant_menu
                if not any(
                    allergen in item.get("allergens", []) for allergen in allergen_free
                )
            ]

        return restaurant_menu
    except HTTPException:
        # Propagate intended HTTP errors
        raise
    except Exception as e:
        print(f"Error fetching menu items: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/restaurants/{restaurant_id}/menu/{menu_item_id}")
async def update_menu_item(
    restaurant_id: str, menu_item_id: str, menu_item: MenuItem, token_data: dict = Depends(verify_token)
):
    try:
        user_id = token_data.get("uid")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user token")
        is_admin = await check_admin_status(token_data)
        if not can_edit_menu(db, user_id, restaurant_id, is_admin):
            raise HTTPException(status_code=403, detail="You don't have permission to edit this menu")

        # Verify restaurant exists
        restaurant_ref = db.reference(f"restaurants/{restaurant_id}")
        restaurant_data = restaurant_ref.get()

        if not restaurant_data:
            raise HTTPException(
                status_code=404, detail=f"Restaurant {restaurant_id} not found"
            )

        # Verify menu item exists and belongs to the restaurant
        menu_ref = db.reference(f"menu_items/{menu_item_id}")
        existing_menu_item_data = menu_ref.get()

        if not existing_menu_item_data:
            raise HTTPException(
                status_code=404, detail=f"Menu item {menu_item_id} not found"
            )

        if existing_menu_item_data.get("restaurant_id") != restaurant_id:
            raise HTTPException(
                status_code=403,
                detail=f"Menu item {menu_item_id} does not belong to restaurant {restaurant_id}",
            )

        # Update menu item data while preserving any existing fields
        # (such as image metadata) that are not part of the MenuItem model.
        menu_item_dict = menu_item.dict(exclude_unset=True)
        updated_menu_item = {
            **(existing_menu_item_data or {}),
            **menu_item_dict,
            "id": menu_item_id,
            "restaurant_id": restaurant_id,
            "archived": bool((existing_menu_item_data or {}).get("archived", False)),
        }

        if "archived" in menu_item_dict:
            updated_menu_item["archived"] = bool(menu_item_dict["archived"])

        # Update in database
        menu_ref.set(updated_menu_item)

        return updated_menu_item

    except HTTPException as he:
        # Re-raise HTTP exceptions as is
        raise he
    except Exception as e:
        print(f"Error updating menu item: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/restaurants/{restaurant_id}/menu/{menu_item_id}/duplicate")
async def duplicate_menu_item(
    restaurant_id: str,
    menu_item_id: str,
    token_data: dict = Depends(verify_token),
):
    try:
        await _authorize_restaurant_access(restaurant_id, token_data)

        menu_ref = db.reference(f"menu_items/{menu_item_id}")
        existing_menu_item_data = menu_ref.get()

        if not existing_menu_item_data:
            raise HTTPException(
                status_code=404, detail=f"Menu item {menu_item_id} not found"
            )

        if existing_menu_item_data.get("restaurant_id") != restaurant_id:
            raise HTTPException(
                status_code=403,
                detail=f"Menu item {menu_item_id} does not belong to restaurant {restaurant_id}",
            )

        new_menu_item_id = generate_id("menu_items")
        duplicated_menu_item = {
            **existing_menu_item_data,
            "id": new_menu_item_id,
            "restaurant_id": restaurant_id,
            "archived": False,
        }
        duplicated_menu_item.pop("image_url", None)

        db.reference("menu_items").child(new_menu_item_id).set(duplicated_menu_item)
        return duplicated_menu_item
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error duplicating menu item: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/restaurants/{restaurant_id}/menu/{menu_item_id}/archive")
async def archive_menu_item(
    restaurant_id: str,
    menu_item_id: str,
    token_data: dict = Depends(verify_token),
):
    try:
        await _authorize_restaurant_access(restaurant_id, token_data)

        menu_ref = db.reference(f"menu_items/{menu_item_id}")
        existing_menu_item_data = menu_ref.get()

        if not existing_menu_item_data:
            raise HTTPException(
                status_code=404, detail=f"Menu item {menu_item_id} not found"
            )

        if existing_menu_item_data.get("restaurant_id") != restaurant_id:
            raise HTTPException(
                status_code=403,
                detail=f"Menu item {menu_item_id} does not belong to restaurant {restaurant_id}",
            )

        updated_menu_item = {
            **existing_menu_item_data,
            "id": menu_item_id,
            "restaurant_id": restaurant_id,
            "archived": True,
        }
        menu_ref.set(updated_menu_item)
        return updated_menu_item
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error archiving menu item: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/restaurants/{restaurant_id}/menu/{menu_item_id}/restore")
async def restore_menu_item(
    restaurant_id: str,
    menu_item_id: str,
    token_data: dict = Depends(verify_token),
):
    try:
        await _authorize_restaurant_access(restaurant_id, token_data)

        menu_ref = db.reference(f"menu_items/{menu_item_id}")
        existing_menu_item_data = menu_ref.get()

        if not existing_menu_item_data:
            raise HTTPException(
                status_code=404, detail=f"Menu item {menu_item_id} not found"
            )

        if existing_menu_item_data.get("restaurant_id") != restaurant_id:
            raise HTTPException(
                status_code=403,
                detail=f"Menu item {menu_item_id} does not belong to restaurant {restaurant_id}",
            )

        updated_menu_item = {
            **existing_menu_item_data,
            "id": menu_item_id,
            "restaurant_id": restaurant_id,
            "archived": False,
        }
        menu_ref.set(updated_menu_item)
        return updated_menu_item
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error restoring menu item: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/restaurants/{restaurant_id}/menu/bulk-update")
async def bulk_update_menu_items(
    restaurant_id: str,
    payload: BulkMenuUpdate,
    token_data: dict = Depends(verify_token),
):
    try:
        await _authorize_restaurant_access(restaurant_id, token_data)

        invalid_allergens = set(payload.add_allergens + payload.remove_allergens) - VALID_ALLERGENS
        if invalid_allergens:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid allergens: {', '.join(sorted(invalid_allergens))}",
            )

        invalid_categories = (
            set(payload.add_dietary_categories + payload.remove_dietary_categories)
            - VALID_DIETARY_CATEGORIES
        )
        if invalid_categories:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid dietary categories: {', '.join(sorted(invalid_categories))}",
            )

        if not payload.item_ids:
            raise HTTPException(status_code=400, detail="No menu item ids provided")

        menu_ref = db.reference("menu_items")
        updated_items = []

        for menu_item_id in payload.item_ids:
            item_ref = menu_ref.child(menu_item_id)
            existing_menu_item_data = item_ref.get()

            if not existing_menu_item_data:
                raise HTTPException(
                    status_code=404, detail=f"Menu item {menu_item_id} not found"
                )

            if existing_menu_item_data.get("restaurant_id") != restaurant_id:
                raise HTTPException(
                    status_code=403,
                    detail=f"Menu item {menu_item_id} does not belong to restaurant {restaurant_id}",
                )

            updated_menu_item = {
                **existing_menu_item_data,
                "id": menu_item_id,
                "restaurant_id": restaurant_id,
                "allergens": _merge_tag_updates(
                    existing_menu_item_data.get("allergens", []),
                    payload.add_allergens,
                    payload.remove_allergens,
                ),
                "dietaryCategories": _merge_tag_updates(
                    existing_menu_item_data.get("dietaryCategories", []),
                    payload.add_dietary_categories,
                    payload.remove_dietary_categories,
                ),
                "archived": bool(existing_menu_item_data.get("archived", False)),
            }
            item_ref.set(updated_menu_item)
            updated_items.append(updated_menu_item)

        return {"updated_count": len(updated_items), "items": updated_items}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error bulk updating menu items: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/restaurants/{restaurant_id}/menu/{menu_item_id}")
async def delete_menu_item(
    restaurant_id: str, menu_item_id: str, token_data: dict = Depends(verify_token)
):
    try:
        user_id = token_data.get("uid")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user token")
        is_admin = await check_admin_status(token_data)
        if not can_edit_menu(db, user_id, restaurant_id, is_admin):
            raise HTTPException(status_code=403, detail="You don't have permission to edit this menu")

        # Verify restaurant exists
        restaurant_ref = db.reference(f"restaurants/{restaurant_id}")
        restaurant_data = restaurant_ref.get()

        if not restaurant_data:
            raise HTTPException(
                status_code=404, detail=f"Restaurant {restaurant_id} not found"
            )

        # Verify menu item exists and belongs to the restaurant
        menu_ref = db.reference(f"menu_items/{menu_item_id}")
        menu_item_data = menu_ref.get()

        if not menu_item_data:
            raise HTTPException(
                status_code=404, detail=f"Menu item {menu_item_id} not found"
            )

        if menu_item_data.get("restaurant_id") != restaurant_id:
            raise HTTPException(
                status_code=403,
                detail=f"Menu item {menu_item_id} does not belong to restaurant {restaurant_id}",
            )

        # Delete the menu item
        menu_ref.delete()

        return {"message": f"Menu item {menu_item_id} successfully deleted"}

    except HTTPException as he:
        # Re-raise HTTP exceptions as is
        raise he
    except Exception as e:
        print(f"Error deleting menu item: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/upload-image")
async def upload_menu_item_image(
    file: UploadFile = File(...),
    menu_item_id: str = Form(...),
    token_data: dict = Depends(verify_token),
):
    """
    Upload an image for a menu item, store it in Firebase Cloud Storage,
    and persist the public URL on the corresponding menu item record.
    """
    try:
        user_id = token_data.get("uid")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user token",
            )

        # Validate MIME type
        allowed_types = {"image/jpeg", "image/png", "image/webp"}
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only JPEG, PNG, and WebP images are allowed.",
            )

        # Read file into memory and enforce size limit
        file_bytes = await file.read()
        if len(file_bytes) > MAX_IMAGE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image exceeds maximum size of 5MB.",
            )

        # Ensure menu item exists
        menu_ref = db.reference(f"menu_items/{menu_item_id}")
        menu_item_data = menu_ref.get()
        if not menu_item_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Menu item {menu_item_id} not found",
            )

        # Authorization: only restaurant owner or admin can modify the image
        restaurant_id = menu_item_data.get("restaurant_id")
        if not restaurant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Menu item is missing restaurant association.",
            )

        restaurant_ref = db.reference(f"restaurants/{restaurant_id}")
        restaurant_data = restaurant_ref.get()
        if not restaurant_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Restaurant {restaurant_id} not found",
            )

        is_admin = await check_admin_status(token_data)
        if restaurant_data.get("owner_uid") != user_id and not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to modify this menu item image.",
            )

        # Determine storage bucket
        bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET")
        bucket = storage.bucket(bucket_name) if bucket_name else storage.bucket()

        # Build a safe, reasonably unique filename
        original_name = file.filename or "image"
        _, ext = os.path.splitext(original_name)
        ext = ext.lower() if ext else ""
        unique_name = f"{uuid4().hex}{ext}"
        blob_path = f"menu_items/{menu_item_id}/{unique_name}"

        blob = bucket.blob(blob_path)
        blob.upload_from_string(file_bytes, content_type=file.content_type)

        # Generate a short-lived signed URL instead of making the object public
        image_url = blob.generate_signed_url(
            expiration=timedelta(hours=1),
            method="GET",
        )

        # Persist path (and last signed URL for convenience) on the menu item record
        menu_ref.update({"image_url": image_url, "image_path": blob_path})

        return {"image_url": image_url}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error uploading menu item image: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload image",
        )


@router.delete("/api/delete-image/{menu_item_id}")
async def delete_menu_item_image(
    menu_item_id: str,
    token_data: dict = Depends(verify_token),
):
    """
    Delete a menu item's image from Firebase Cloud Storage and clear
    the stored URL on the corresponding database record.
    """
    try:
        user_id = token_data.get("uid")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user token",
            )

        # Locate the menu item
        menu_ref = db.reference(f"menu_items/{menu_item_id}")
        menu_item_data = menu_ref.get()
        if not menu_item_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Menu item {menu_item_id} not found",
            )

        restaurant_id = menu_item_data.get("restaurant_id")
        if not restaurant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Menu item is missing restaurant association.",
            )

        restaurant_ref = db.reference(f"restaurants/{restaurant_id}")
        restaurant_data = restaurant_ref.get()
        if not restaurant_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Restaurant {restaurant_id} not found",
            )

        is_admin = await check_admin_status(token_data)
        if restaurant_data.get("owner_uid") != user_id and not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to modify this menu item image.",
            )

        image_path = menu_item_data.get("image_path")

        # Best-effort deletion from Cloud Storage if we know the path
        if image_path:
            try:
                bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET")
                bucket = storage.bucket(bucket_name) if bucket_name else storage.bucket()
                blob = bucket.blob(image_path)
                blob.delete()
            except Exception as storage_error:
                print(f"Error deleting image blob for menu item {menu_item_id}: {storage_error}")

        # Clear image fields on the menu item record
        menu_ref.update({"image_url": None, "image_path": None})

        return {"message": f"Image for menu item {menu_item_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting menu item image: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete image",
        )
