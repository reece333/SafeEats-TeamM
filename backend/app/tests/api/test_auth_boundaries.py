from fastapi.testclient import TestClient

import routes as app_routes


def test_missing_token_401(client: TestClient):
    resp = client.get("/restaurants")
    assert resp.status_code == 401
    body = resp.json()
    assert "Missing or invalid authorization header" in body.get("detail", "")


def test_expired_token_401(client: TestClient):
    resp = client.get("/restaurants", headers={"Authorization": "Bearer expired"})
    assert resp.status_code == 401
    body = resp.json()
    assert "Invalid or expired token" in body.get("detail", "")


def test_wrong_restaurant_forbidden_403(client: TestClient, user_auth_header, fake_db):
    # Seed a restaurant owned by someone else
    fake_db.reference("restaurants").child("r2").set(
        {
            "name": "Other",
            "address": "addr",
            "phone": "000",
            "cuisine_type": "x",
            "owner_uid": "someone_else",
        }
    )
    resp = client.get("/restaurants/r2/menu", headers=user_auth_header)
    assert resp.status_code == 403
    assert "permission" in resp.json().get("detail", "").lower()


def test_admin_can_access_other_restaurant(client: TestClient, admin_auth_header, fake_db):
    # Seed a restaurant owned by someone else
    fake_db.reference("restaurants").child("r3").set(
        {
            "name": "Other3",
            "address": "addr",
            "phone": "000",
            "cuisine_type": "x",
            "owner_uid": "third_party",
        }
    )
    resp = client.get("/restaurants/r3/menu", headers=admin_auth_header)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)




