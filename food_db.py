from typing import Any


FOOD_DATABASE: dict[str, dict[str, Any]] = {
    "Roti": {
        "serving": "1 medium",
        "carbs": 18.0,
        "protein": 3.0,
        "fat": 2.0,
        "fiber": 2.0,
        "calories": 95.0,
    },
    "Rice": {
        "serving": "1 cup cooked",
        "carbs": 45.0,
        "protein": 4.0,
        "fat": 0.4,
        "fiber": 0.6,
        "calories": 205.0,
    },
    "Dal": {
        "serving": "1 katori",
        "carbs": 18.0,
        "protein": 9.0,
        "fat": 3.0,
        "fiber": 6.0,
        "calories": 140.0,
    },
    "Sabzi": {
        "serving": "1 cup",
        "carbs": 12.0,
        "protein": 3.0,
        "fat": 5.0,
        "fiber": 4.0,
        "calories": 105.0,
    },
    "Paneer": {
        "serving": "100 g",
        "carbs": 6.0,
        "protein": 18.0,
        "fat": 20.0,
        "fiber": 0.0,
        "calories": 265.0,
    },
    "Dosa": {
        "serving": "1 plain dosa",
        "carbs": 28.0,
        "protein": 4.0,
        "fat": 6.0,
        "fiber": 2.0,
        "calories": 168.0,
    },
    "Idli": {
        "serving": "2 pieces",
        "carbs": 28.0,
        "protein": 5.0,
        "fat": 1.0,
        "fiber": 2.0,
        "calories": 146.0,
    },
    "Poha": {
        "serving": "1 cup",
        "carbs": 32.0,
        "protein": 5.0,
        "fat": 8.0,
        "fiber": 3.0,
        "calories": 220.0,
    },
    "Upma": {
        "serving": "1 cup",
        "carbs": 30.0,
        "protein": 6.0,
        "fat": 7.0,
        "fiber": 4.0,
        "calories": 210.0,
    },
    "Curd": {
        "serving": "1 cup",
        "carbs": 8.0,
        "protein": 8.0,
        "fat": 5.0,
        "fiber": 0.0,
        "calories": 98.0,
    },
    "Chai": {
        "serving": "1 cup",
        "carbs": 10.0,
        "protein": 2.0,
        "fat": 2.0,
        "fiber": 0.0,
        "calories": 70.0,
    },
    "Oats": {
        "serving": "1 bowl cooked",
        "carbs": 27.0,
        "protein": 5.0,
        "fat": 3.0,
        "fiber": 4.0,
        "calories": 160.0,
    },
    "Banana": {
        "serving": "1 medium",
        "carbs": 27.0,
        "protein": 1.3,
        "fat": 0.3,
        "fiber": 3.0,
        "calories": 105.0,
    },
    "Eggs": {
        "serving": "2 whole eggs",
        "carbs": 1.0,
        "protein": 12.0,
        "fat": 10.0,
        "fiber": 0.0,
        "calories": 140.0,
    },
}


def get_food_choices() -> list[str]:
    return list(FOOD_DATABASE.keys())


def get_food(food_name: str) -> dict[str, Any]:
    if food_name not in FOOD_DATABASE:
        raise KeyError(f"Unknown food item: {food_name}")

    item = FOOD_DATABASE[food_name].copy()
    item["name"] = food_name
    return item


def calculate_food_macros(food_name: str, servings: float = 1.0) -> dict[str, float]:
    item = get_food(food_name)
    return {
        "carbs": round(item["carbs"] * servings, 1),
        "protein": round(item["protein"] * servings, 1),
        "fat": round(item["fat"] * servings, 1),
        "fiber": round(item["fiber"] * servings, 1),
        "calories": round(item["calories"] * servings, 1),
    }
