"""Tests for /auth routes: login, register, user, admin, team, logout."""
import types

import pytest
from fastapi.testclient import TestClient

import auth_routes as app_auth


def test_root_message(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200
    assert "message" in r.json()


def test_get_current_user_ok(client: TestClient, user_auth_header):
    r = client.get("/auth/user", headers=user_auth_header)
    assert r.status_code == 200
    body = r.json()
    assert body["uid"] == "user1"
    assert body["email"]  # from Firebase Auth stub (e.g. user1@example.com)
    assert "restaurants" in body


def test_get_users_forbidden_for_non_admin(client: TestClient, user_auth_header):
    r = client.get("/auth/users", headers=user_auth_header)
    assert r.status_code == 403


def test_get_users_ok_for_admin(client: TestClient, admin_auth_header, fake_db):
    r = client.get("/auth/users", headers=admin_auth_header)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    uids = {u["uid"] for u in data}
    assert "user1" in uids


def test_login_ok(monkeypatch, client: TestClient, fake_db):
    monkeypatch.setattr(
        app_auth.auth,
        "get_user_by_email",
        lambda email: types.SimpleNamespace(uid="user1", email=email),
    )
    r = client.post(
        "/auth/login",
        json={"email": "u1@example.com", "password": "does-not-matter-for-stub"},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["uid"] == "user1"
    assert j["token"]


def test_register_ok(monkeypatch, client: TestClient, fake_db):
    created = {}

    def fake_create_user(**kwargs):
        created.update(kwargs)
        return types.SimpleNamespace(uid="newuser99", email=kwargs["email"])

    monkeypatch.setattr(app_auth.auth, "create_user", fake_create_user)
    r = client.post(
        "/auth/register",
        json={
            "email": "brandnew@example.com",
            "password": "password1",
            "name": "Brand New",
        },
    )
    assert r.status_code == 200
    j = r.json()
    assert j["uid"] == "newuser99"
    assert j["email"] == "brandnew@example.com"
    assert j["token"]
    assert created.get("email") == "brandnew@example.com"


def test_logout_returns_ok(client: TestClient, user_auth_header):
    r = client.post("/auth/logout", headers=user_auth_header)
    assert r.status_code == 200


def test_make_admin_by_user_id(monkeypatch, client: TestClient, fake_db, admin_auth_header):
    monkeypatch.setattr(
        app_auth.auth,
        "get_user",
        lambda uid: types.SimpleNamespace(uid=uid, email=f"{uid}@x.com"),
    )
    r = client.post("/auth/make-admin/user1", headers=admin_auth_header)
    assert r.status_code == 200
    row = fake_db.reference("users").child("user1").get()
    assert row.get("is_admin") is True


def test_make_admin_by_email(monkeypatch, client: TestClient, fake_db, admin_auth_header):
    monkeypatch.setattr(
        app_auth.auth,
        "get_user_by_email",
        lambda email: types.SimpleNamespace(uid="staff1", email=email),
    )
    fake_db.reference("users").child("staff1").update({"is_admin": False})
    r = client.post(
        "/auth/make-admin-by-email",
        headers=admin_auth_header,
        json={"email": "staff@example.com"},
    )
    assert r.status_code == 200
    assert fake_db.reference("users").child("staff1").get().get("is_admin") is True


def test_invite_and_remove_member(monkeypatch, client: TestClient, user_auth_header, fake_db):
    fake_db.reference("restaurants").set({})
    fake_db.reference("restaurant_members").set({})
    cr = client.post(
        "/restaurants/",
        headers=user_auth_header,
        json={
            "name": "Invite Test",
            "phone": "1",
            "address": "a",
            "cuisine_type": "c",
        },
    )
    rid = cr.json()["id"]

    monkeypatch.setattr(
        app_auth.auth,
        "get_user_by_email",
        lambda email: types.SimpleNamespace(uid="staff1", email=email),
    )
    inv = client.post(
        f"/auth/restaurants/{rid}/members",
        headers=user_auth_header,
        json={"email": "staff@example.com", "role": "staff"},
    )
    assert inv.status_code == 200
    mem = fake_db.reference(f"restaurant_members/{rid}").get() or {}
    assert "staff1" in mem

    rem = client.delete(
        f"/auth/restaurants/{rid}/members/staff1",
        headers=user_auth_header,
    )
    assert rem.status_code == 200
    mem2 = fake_db.reference(f"restaurant_members/{rid}").get() or {}
    assert "staff1" not in mem2


def test_invite_invalid_role(client: TestClient, user_auth_header, fake_db):
    fake_db.reference("restaurants").set({})
    cr = client.post(
        "/restaurants/",
        headers=user_auth_header,
        json={"name": "R", "phone": "1", "address": "a", "cuisine_type": "c"},
    )
    rid = cr.json()["id"]
    r = client.post(
        f"/auth/restaurants/{rid}/members",
        headers=user_auth_header,
        json={"email": "staff@example.com", "role": "chef"},
    )
    assert r.status_code == 400


def test_cannot_remove_owner_from_members(client: TestClient, user_auth_header, fake_db):
    fake_db.reference("restaurants").set({})
    cr = client.post(
        "/restaurants/",
        headers=user_auth_header,
        json={"name": "R2", "phone": "1", "address": "a", "cuisine_type": "c"},
    )
    rid = cr.json()["id"]
    r = client.delete(
        f"/auth/restaurants/{rid}/members/user1",
        headers=user_auth_header,
    )
    assert r.status_code == 400
