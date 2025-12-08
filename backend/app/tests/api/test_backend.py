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