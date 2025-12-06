import types

from fastapi.testclient import TestClient

import routes as app_routes


def test_ingest_menu_timeout_returns_504(client: TestClient, user_auth_header, monkeypatch):
    # Stub genai with a model whose generate_content always times out
    class DummyModel:
        def __init__(self, *args, **kwargs):
            pass

        def generate_content(self, *args, **kwargs):
            raise TimeoutError("deadline exceeded")

    stub_genai = types.SimpleNamespace(
        GenerativeModel=DummyModel,
        list_models=lambda: [],
    )
    app_routes.genai = stub_genai  # type: ignore
    # Bypass configuration and model-name selection
    app_routes._ensure_genai_configured = lambda: None  # type: ignore
    app_routes._select_model_name = lambda: "dummy"  # type: ignore

    files = {"file": ("menu.png", b"123", "image/png")}
    resp = client.post("/ai/ingest-menu", headers=user_auth_header, files=files)
    assert resp.status_code == 504
    assert resp.json() == {"error": "upstream_timeout"}


def test_parse_ingredients_non_utf8_body_returns_400(client: TestClient, user_auth_header):
    # Send invalid bytes under application/json
    resp = client.post(
        "/ai/parse-ingredients",
        headers={**user_auth_header, "Content-Type": "application/json"},
        data=b"\x80\x81",
    )
    # FastAPI/Starlette typically returns 400 for invalid JSON encoding
    assert resp.status_code == 400


def test_parse_ingredients_missing_field_returns_422(client: TestClient, user_auth_header):
    # Missing required "ingredients" field triggers validation error
    resp = client.post(
        "/ai/parse-ingredients",
        headers={**user_auth_header, "Content-Type": "application/json"},
        json={},
    )
    assert resp.status_code == 422




