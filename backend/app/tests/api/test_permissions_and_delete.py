"""Permissions helpers via API; delete restaurant cleans menu_items."""
from fastapi.testclient import TestClient


def test_delete_restaurant_removes_menu_items(client: TestClient, user_auth_header, fake_db):
    fake_db.reference("restaurants").set({})
    fake_db.reference("menu_items").set({})
    r = client.post(
        "/restaurants/",
        headers=user_auth_header,
        json={
            "name": "Wipe Me",
            "phone": "1",
            "address": "a",
            "cuisine_type": "c",
        },
    )
    rid = r.json()["id"]
    m = client.post(
        f"/restaurants/{rid}/menu",
        headers=user_auth_header,
        json={
            "name": "Item",
            "description": "d",
            "price": 1.0,
            "allergens": [],
            "dietaryCategories": [],
        },
    )
    mid = m.json()["id"]
    assert fake_db.reference("menu_items").child(mid).get() is not None

    d = client.delete(f"/restaurants/{rid}", headers=user_auth_header)
    assert d.status_code == 200
    assert fake_db.reference("restaurants").child(rid).get() is None
    assert fake_db.reference("menu_items").child(mid).get() is None


def test_post_menu_invalid_allergen_400(client: TestClient, user_auth_header, fake_db):
    fake_db.reference("restaurants").set({})
    cr = client.post(
        "/restaurants/",
        headers=user_auth_header,
        json={"name": "R", "phone": "1", "address": "a", "cuisine_type": "c"},
    )
    rid = cr.json()["id"]
    r = client.post(
        f"/restaurants/{rid}/menu",
        headers=user_auth_header,
        json={
            "name": "Bad",
            "description": "d",
            "price": 1.0,
            "allergens": ["not_a_real_allergen"],
            "dietaryCategories": [],
        },
    )
    assert r.status_code == 400


def test_get_restaurants_admin_sees_all(client: TestClient, admin_auth_header, fake_db):
    fake_db.reference("restaurants").set(
        {
            "a1": {
                "name": "A",
                "address": "x",
                "phone": "1",
                "cuisine_type": "c",
                "owner_uid": "other",
            }
        }
    )
    r = client.get("/restaurants", headers=admin_auth_header)
    assert r.status_code == 200
    ids = {x["id"] for x in r.json()}
    assert "a1" in ids
