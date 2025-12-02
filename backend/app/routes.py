from fastapi import APIRouter, HTTPException, Depends
from firebase_admin import db
import random
from models import Restaurant, MenuItem
from typing import List, Optional
from auth_routes import verify_token
import os
import json
from pydantic import BaseModel

try:
    import google.generativeai as genai
except Exception:
    genai = None

router = APIRouter()


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
                response = model.generate_content(prompt)
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

        # Admins can see all restaurants, others only see their own
        if is_admin:
            # Return all restaurants for admins
            restaurants = [
                {"id": str(restaurant_id), **restaurant_data}
                for restaurant_id, restaurant_data in all_restaurants.items()
            ]
        else:
            # Filter restaurants by owner_uid for regular users
            restaurants = [
                {"id": str(restaurant_id), **restaurant_data}
                for restaurant_id, restaurant_data in all_restaurants.items()
                if restaurant_data.get("owner_uid") == user_id
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

        # Verify ownership or admin status
        if restaurant_data.get("owner_uid") != user_id and not is_admin:
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

        # Verify ownership or admin status
        if restaurant_data.get("owner_uid") != user_id and not is_admin:
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

        # Verify ownership or admin status
        if restaurant_data.get("owner_uid") != user_id and not is_admin:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to modify this restaurant's menu",
            )

        # Validate allergens and dietary categories
        valid_allergens = {
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
        valid_dietary_categories = {"vegan", "vegetarian"}

        # Validate allergens
        invalid_allergens = set(menu_item.allergens) - valid_allergens
        if invalid_allergens:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid allergens: {', '.join(invalid_allergens)}",
            )

        # Validate dietary categories
        invalid_categories = set(menu_item.dietaryCategories) - valid_dietary_categories
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

        # Verify ownership or admin status
        if restaurant_data.get("owner_uid") != user_id and not is_admin:
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
            {"id": str(item_id), **item_data}
            for item_id, item_data in menu_items.items()
            if item_data.get("restaurant_id") == restaurant_id
        ]

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

    except Exception as e:
        print(f"Error fetching menu items: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/restaurants/{restaurant_id}/menu/{menu_item_id}")
async def update_menu_item(restaurant_id: str, menu_item_id: str, menu_item: MenuItem):
    try:
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

        # Update menu item data while preserving ID and restaurant_id
        menu_item_dict = menu_item.dict()
        updated_menu_item = {
            **menu_item_dict,
            "id": menu_item_id,
            "restaurant_id": restaurant_id,
        }

        # Update in database
        menu_ref.set(updated_menu_item)

        return updated_menu_item

    except HTTPException as he:
        # Re-raise HTTP exceptions as is
        raise he
    except Exception as e:
        print(f"Error updating menu item: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/restaurants/{restaurant_id}/menu/{menu_item_id}")
async def delete_menu_item(restaurant_id: str, menu_item_id: str):
    try:
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
