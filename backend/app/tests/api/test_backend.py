from fastapi.testclient import TestClient

import routes as app_routes

def test_restaurants_get_empty(client: TestClient, user_auth_header, fake_db):
    fake_db.reference("restaurants").set({})
    resp = client.get("/restaurants", headers=user_auth_header)
    assert resp.status_code == 200
    assert resp.json() == []

def test_restaurant_create_and_get(client: TestClient, user_auth_header, fake_db):
    fake_db.reference("restaurants").set({})
    resp1 = client.post("/restaurants/", headers=user_auth_header, json={
        "name": "Lorem Ipsum",
        "phone": "+1 123-456-7890",
        "address": "200 E Cameron Ave, Chapel Hill, NC 27514",
        "cuisine_type": "American"
    })
    assert resp1.status_code == 200
    id = resp1.json()['id']
    
    resp2 = client.get(f"/restaurants/{id}", headers=user_auth_header)
    assert resp2.status_code == 200
    assert resp2.json()['address'] == "200 E Cameron Ave, Chapel Hill, NC 27514"
    assert resp2.json()['owner_uid'] == 'user1'

def test_restaurant_create_and_list(client: TestClient, user_auth_header, fake_db):
    fake_db.reference("restaurants").set({})
    resp1 = client.post("/restaurants/", headers=user_auth_header, json={
        "name": "Lorem Ipsum",
        "phone": "+1 123-456-7890",
        "address": "200 E Cameron Ave, Chapel Hill, NC 27514",
        "cuisine_type": "American"
    })
    assert resp1.status_code == 200

    resp2 = client.get(f"/restaurants", headers=user_auth_header)
    assert resp2.status_code == 200
    assert len(resp2.json()) == 1

def test_restaurant_update(client: TestClient, user_auth_header, fake_db):
    fake_db.reference("restaurants").set({})
    resp1 = client.post("/restaurants/", headers=user_auth_header, json={
        "name": "Lorem Ipsum",
        "phone": "+1 123-456-7890",
        "address": "200 E Cameron Ave, Chapel Hill, NC 27514",
        "cuisine_type": "American"
    })
    assert resp1.status_code == 200
    id = resp1.json()['id']

    resp2 = client.put(f"/restaurants/{id}", headers=user_auth_header, json={
        "name": "Lorem Ipsum",
        "phone": "+1 123-456-7890",
        "address": "200 E Cameron Ave, Chapel Hill, NC 27514",
        "cuisine_type": "North Carolinian"
    })
    assert resp2.status_code == 200

    resp3 = client.get(f"/restaurants/{id}", headers=user_auth_header)
    assert resp3.status_code == 200
    assert resp3.json()['address'] == "200 E Cameron Ave, Chapel Hill, NC 27514"
    assert resp3.json()['cuisine_type'] == 'North Carolinian'

def test_restaurant_delete(client: TestClient, user_auth_header, fake_db):
    fake_db.reference("restaurants").set({})
    resp1 = client.post("/restaurants/", headers=user_auth_header, json={
        "name": "Lorem Ipsum",
        "phone": "+1 123-456-7890",
        "address": "200 E Cameron Ave, Chapel Hill, NC 27514",
        "cuisine_type": "American"
    })
    assert resp1.status_code == 200
    id = resp1.json()['id']

    resp2 = client.put(f"/restaurants/{id}", headers=user_auth_header, json={
        "name": "Lorem Ipsum",
        "phone": "+1 123-456-7890",
        "address": "200 E Cameron Ave, Chapel Hill, NC 27514",
        "cuisine_type": "North Carolinian"
    })
    assert resp2.status_code == 200

    resp3 = client.get(f"/restaurants/{id}", headers=user_auth_header)
    assert resp3.status_code == 200
    assert resp3.json()['address'] == "200 E Cameron Ave, Chapel Hill, NC 27514"
    assert resp3.json()['cuisine_type'] == 'North Carolinian'

def test_restaurant_menu_create_and_get(client: TestClient, user_auth_header, fake_db):
    fake_db.reference("restaurants").set({})
    resp1 = client.post("/restaurants/", headers=user_auth_header, json={
        "name": "Lorem Ipsum",
        "phone": "+1 123-456-7890",
        "address": "200 E Cameron Ave, Chapel Hill, NC 27514",
        "cuisine_type": "American"
    })
    assert resp1.status_code == 200
    id = resp1.json()['id']
    
    resp2 = client.post(f"/restaurants/{id}/menu", headers=user_auth_header, json={
        "name": "Fishy Fish",
        "description": "Tasty, delicious fish. Guaranteed rat meat free!",
        "price": 17.95,
        "allergens": ["fish"],
        "dietaryCategories": []
    })
    assert resp2.status_code == 200

    resp3 = client.get(f"/restaurants/{id}/menu", headers=user_auth_header)
    resp3j = resp3.json()
    assert len(resp3j) == 1
    assert resp3j[0]["allergens"] == ["fish"]

    resp4 = client.get(f"/restaurants/{id}/menu?dietary_category=vegan", headers=user_auth_header)
    resp4j = resp4.json()
    assert len(resp4j) == 0

def test_restaurant_menu_update(client: TestClient, user_auth_header, fake_db):
    fake_db.reference("restaurants").set({})
    resp1 = client.post("/restaurants/", headers=user_auth_header, json={
        "name": "Lorem Ipsum",
        "phone": "+1 123-456-7890",
        "address": "200 E Cameron Ave, Chapel Hill, NC 27514",
        "cuisine_type": "American"
    })
    assert resp1.status_code == 200
    id = resp1.json()['id']
    
    resp2 = client.post(f"/restaurants/{id}/menu", headers=user_auth_header, json={
        "name": "Fishy Fish",
        "description": "Tasty, delicious fish. Guaranteed rat meat free!",
        "price": 17.95,
        "allergens": ["fish"],
        "dietaryCategories": []
    })
    assert resp2.status_code == 200
    mid = resp2.json()['id']

    resp3 = client.put(f"/restaurants/{id}/menu/{mid}", headers=user_auth_header, json={
        "name": "Fishy Fish",
        "description": "Turns out the fishy fish didn't actually contain fish.",
        "price": 1.795,
        "allergens": [],
        "dietaryCategories": []
    })
    assert resp3.status_code == 200

    resp4 = client.get(f"/restaurants/{id}/menu", headers=user_auth_header)
    resp4j = resp4.json()
    assert resp4.status_code == 200
    assert len(resp4j) == 1
    assert resp4j[0]["allergens"] == []
    assert resp4j[0]["price"] == 1.795
    assert resp4j[0]["name"] == "Fishy Fish"

def test_restaurant_menu_delete(client: TestClient, user_auth_header, fake_db):
    fake_db.reference("restaurants").set({})
    resp1 = client.post("/restaurants/", headers=user_auth_header, json={
        "name": "Lorem Ipsum",
        "phone": "+1 123-456-7890",
        "address": "200 E Cameron Ave, Chapel Hill, NC 27514",
        "cuisine_type": "American"
    })
    assert resp1.status_code == 200
    id = resp1.json()['id']
    
    resp2 = client.post(f"/restaurants/{id}/menu", headers=user_auth_header, json={
        "name": "Fishy Fish",
        "description": "Tasty, delicious fish. Guaranteed rat meat free!",
        "price": 17.95,
        "allergens": ["fish"],
        "dietaryCategories": []
    })
    assert resp2.status_code == 200
    mid = resp2.json()['id']

    resp3 = client.delete(f"/restaurants/{id}/menu/{mid}", headers=user_auth_header)
    assert resp3.status_code == 200

    resp4 = client.get(f"/restaurants/{id}/menu", headers=user_auth_header)
    resp4j = resp4.json()
    assert resp4.status_code == 200
    assert len(resp4j) == 0


def test_owner_can_delete_restaurant(client: TestClient, user_auth_header, fake_db):
    fake_db.reference("restaurants").set({})
    r = client.post(
        "/restaurants/",
        headers=user_auth_header,
        json={
            "name": "To Delete",
            "phone": "555",
            "address": "Here",
            "cuisine_type": "Any",
        },
    )
    assert r.status_code == 200
    rid = r.json()["id"]
    d = client.delete(f"/restaurants/{rid}", headers=user_auth_header)
    assert d.status_code == 200
    gone = client.get(f"/restaurants/{rid}", headers=user_auth_header)
    assert gone.status_code == 404


def test_non_owner_cannot_delete_restaurant(
    client: TestClient, user_auth_header, staff_auth_header, fake_db
):
    fake_db.reference("restaurants").set({})
    r = client.post(
        "/restaurants/",
        headers=user_auth_header,
        json={
            "name": "Owned By User1",
            "phone": "555",
            "address": "There",
            "cuisine_type": "Any",
        },
    )
    rid = r.json()["id"]
    fake_db.reference(f"restaurant_members/{rid}").set(
        {"staff1": {"role": "manager"}}
    )
    d = client.delete(f"/restaurants/{rid}", headers=staff_auth_header)
    assert d.status_code == 403
    still = client.get(f"/restaurants/{rid}", headers=user_auth_header)
    assert still.status_code == 200