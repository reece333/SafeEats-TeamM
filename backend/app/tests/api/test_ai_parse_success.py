"""Happy-path test for AI parse-ingredients with stubbed Gemini."""
import types

import routes as app_routes
from fastapi.testclient import TestClient


def test_parse_ingredients_returns_json(monkeypatch, client: TestClient, user_auth_header):
    class FakeResponse:
        text = (
            '{"allergens":["milk"],"dietaryCategories":["vegetarian"],'
            '"extractedIngredients":["cream","sugar"]}'
        )

    class FakeModel:
        def __init__(self, *args, **kwargs):
            pass

        def generate_content(self, *args, **kwargs):
            return FakeResponse()

    stub = types.SimpleNamespace(
        GenerativeModel=FakeModel,
        configure=lambda **kw: None,
        list_models=lambda: [],
    )
    monkeypatch.setattr(app_routes, "genai", stub)

    r = client.post(
        "/ai/parse-ingredients",
        headers={**user_auth_header, "Content-Type": "application/json"},
        json={"ingredients": "cream and sugar"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "milk" in data.get("allergens", [])
    assert "vegetarian" in data.get("dietaryCategories", [])
    assert data.get("extractedIngredients")


def test_ingest_menu_missing_file_422(client: TestClient, user_auth_header):
    r = client.post("/ai/ingest-menu", headers=user_auth_header)
    assert r.status_code == 422
