from functools import lru_cache

INGREDIENT_VARIANTS = {
    "parm": "parmesan",
    "parmigiano reggiano": "parmesan",
    "cheddar": "cheese",
    "mozzarella": "cheese",
    "crab": "crab",
    "shrimp": "shrimp",
    "bacon": "bacon",
}

ALLERGEN_RULES = {
    "cheese": {
        "allergens": ["dairy"],
        "dietaryCategories": ["not vegan"],
    },
    "parmesan": {
        "allergens": ["dairy"],
        "dietaryCategories": ["not vegan"],
    },
    "crab": {
        "allergens": ["shellfish"],
        "dietaryCategories": ["not vegetarian", "not vegan"],
    },
    "shrimp": {
        "allergens": ["shellfish"],
        "dietaryCategories": ["not vegetarian", "not vegan"],
    },
    "bacon": {
        "allergens": [],
        "dietaryCategories": ["not vegetarian", "not vegan"],
    },
}


def split_ingredients(ingredients: str | list[str]) -> list[str]:
    if isinstance(ingredients, str):
        return [
            ingredient.strip()
            for ingredient in ingredients.split(",")
            if ingredient.strip()
        ]

    return ingredients


def normalize_ingredient(ingredient: str) -> str:
    cleaned = ingredient.strip().lower()
    return INGREDIENT_VARIANTS.get(cleaned, cleaned)


@lru_cache(maxsize=500)
def parse_ingredient(ingredient: str) -> dict:
    normalized = normalize_ingredient(ingredient)

    rules = ALLERGEN_RULES.get(
        normalized,
        {
            "allergens": [],
            "dietaryCategories": [],
        },
    )

    return {
        "original_ingredient": ingredient,
        "normalized_ingredient": normalized,
        "allergens": rules["allergens"],
        "dietaryCategories": rules["dietaryCategories"],
    }


def parse_ingredients(ingredients: str | list[str]) -> dict:
    ingredient_list = split_ingredients(ingredients)

    allergens = set()
    dietary_categories = set()
    parsed = []

    for ingredient in ingredient_list:
        result = parse_ingredient(ingredient)
        parsed.append(result)
        allergens.update(result["allergens"])
        dietary_categories.update(result["dietaryCategories"])

    return {
        "parsed_ingredients": parsed,
        "allergens": sorted(allergens),
        "dietaryCategories": sorted(dietary_categories),
    }