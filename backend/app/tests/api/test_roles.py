"""
Tests for multi-user roles: manager (full control) vs staff (menu only).
"""
from fastapi.testclient import TestClient


def test_staff_can_view_and_edit_menu(client: TestClient, user_auth_header, staff_auth_header, fake_db):
    """Manager creates restaurant and adds staff; staff can get menu and add item."""
    fake_db.reference("restaurants").set({})
    fake_db.reference("restaurant_members").set({})
    # User1 (manager) creates restaurant
    r = client.post("/restaurants/", headers=user_auth_header, json={
        "name": "Cafe",
        "phone": "123",
        "address": "456",
        "cuisine_type": "American"
    })
    assert r.status_code == 200
    rid = r.json()["id"]
    # Add staff1 as staff for this restaurant
    fake_db.reference(f"restaurant_members/{rid}").set({"staff1": {"role": "staff"}})
    # Staff can get menu
    r2 = client.get(f"/restaurants/{rid}/menu", headers=staff_auth_header)
    assert r2.status_code == 200
    assert r2.json() == []
    # Staff can add menu item
    r3 = client.post(f"/restaurants/{rid}/menu", headers=staff_auth_header, json={
        "name": "Salad",
        "description": "Green",
        "price": 5.99,
        "allergens": [],
        "dietaryCategories": ["vegan"]
    })
    assert r3.status_code == 200
    # Staff can get restaurant (view)
    r4 = client.get(f"/restaurants/{rid}", headers=staff_auth_header)
    assert r4.status_code == 200


def test_staff_cannot_update_restaurant(client: TestClient, user_auth_header, staff_auth_header, fake_db):
    """Staff gets 403 when updating restaurant profile."""
    fake_db.reference("restaurants").set({})
    fake_db.reference("restaurant_members").set({})
    r = client.post("/restaurants/", headers=user_auth_header, json={
        "name": "Cafe",
        "phone": "123",
        "address": "456",
        "cuisine_type": "American"
    })
    assert r.status_code == 200
    rid = r.json()["id"]
    fake_db.reference(f"restaurant_members/{rid}").set({"staff1": {"role": "staff"}})
    r2 = client.put(f"/restaurants/{rid}", headers=staff_auth_header, json={
        "name": "Cafe Updated",
        "phone": "123",
        "address": "456",
        "cuisine_type": "American"
    })
    assert r2.status_code == 403
    assert "permission" in r2.json().get("detail", "").lower()


def test_staff_cannot_list_or_invite_members(client: TestClient, user_auth_header, staff_auth_header, fake_db):
    """Staff gets 403 on GET/POST restaurant members."""
    fake_db.reference("restaurants").set({})
    fake_db.reference("restaurant_members").set({})
    r = client.post("/restaurants/", headers=user_auth_header, json={
        "name": "Cafe",
        "phone": "123",
        "address": "456",
        "cuisine_type": "American"
    })
    assert r.status_code == 200
    rid = r.json()["id"]
    fake_db.reference(f"restaurant_members/{rid}").set({"staff1": {"role": "staff"}})
    r2 = client.get(f"/auth/restaurants/{rid}/members", headers=staff_auth_header)
    assert r2.status_code == 403
    r3 = client.post(f"/auth/restaurants/{rid}/members", headers=staff_auth_header, json={
        "email": "other@example.com",
        "role": "staff"
    })
    assert r3.status_code == 403


def test_manager_can_update_restaurant_and_list_members(client: TestClient, user_auth_header, fake_db):
    """Manager (owner) can update restaurant and get members list."""
    fake_db.reference("restaurants").set({})
    fake_db.reference("restaurant_members").set({})
    r = client.post("/restaurants/", headers=user_auth_header, json={
        "name": "Cafe",
        "phone": "123",
        "address": "456",
        "cuisine_type": "American"
    })
    assert r.status_code == 200
    rid = r.json()["id"]
    r2 = client.put(f"/restaurants/{rid}", headers=user_auth_header, json={
        "name": "Cafe Updated",
        "phone": "123",
        "address": "456",
        "cuisine_type": "American"
    })
    assert r2.status_code == 200
    r3 = client.get(f"/auth/restaurants/{rid}/members", headers=user_auth_header)
    assert r3.status_code == 200
    assert "members" in r3.json()
    # Creator is owner and appears as manager
    members = r3.json()["members"]
    assert any(m.get("uid") == "user1" and m.get("role") == "manager" for m in members)


def test_staff_can_update_and_delete_menu_item(client: TestClient, user_auth_header, staff_auth_header, fake_db):
    """Staff can PUT and DELETE menu items."""
    fake_db.reference("restaurants").set({})
    fake_db.reference("restaurant_members").set({})
    fake_db.reference("menu_items").set({})
    r = client.post("/restaurants/", headers=user_auth_header, json={
        "name": "Cafe",
        "phone": "123",
        "address": "456",
        "cuisine_type": "American"
    })
    assert r.status_code == 200
    rid = r.json()["id"]
    fake_db.reference(f"restaurant_members/{rid}").set({"staff1": {"role": "staff"}})
    r2 = client.post(f"/restaurants/{rid}/menu", headers=staff_auth_header, json={
        "name": "Soup",
        "description": "Hot",
        "price": 3.99,
        "allergens": [],
        "dietaryCategories": []
    })
    assert r2.status_code == 200
    mid = r2.json()["id"]
    r3 = client.put(f"/restaurants/{rid}/menu/{mid}", headers=staff_auth_header, json={
        "name": "Soup Updated",
        "description": "Hot",
        "price": 4.99,
        "allergens": [],
        "dietaryCategories": []
    })
    assert r3.status_code == 200
    r4 = client.delete(f"/restaurants/{rid}/menu/{mid}", headers=staff_auth_header)
    assert r4.status_code == 200


def test_staff_without_access_gets_403(client: TestClient, user_auth_header, staff_auth_header, fake_db):
    """Staff with no membership gets 403 on that restaurant."""
    fake_db.reference("restaurants").set({})
    fake_db.reference("restaurant_members").set({})
    r = client.post("/restaurants/", headers=user_auth_header, json={
        "name": "Cafe",
        "phone": "123",
        "address": "456",
        "cuisine_type": "American"
    })
    assert r.status_code == 200
    rid = r.json()["id"]
    # Do NOT add staff1 to members
    r2 = client.get(f"/restaurants/{rid}/menu", headers=staff_auth_header)
    assert r2.status_code == 403
