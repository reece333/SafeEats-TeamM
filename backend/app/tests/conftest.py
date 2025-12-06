import os
import types
import copy
from typing import Any, Dict, List, Optional, Tuple

import pytest
from fastapi.testclient import TestClient

import sys


def _install_firebase_stubs():
    """Install minimal firebase_admin stubs into sys.modules before app import."""
    # Exceptions used by auth_routes
    class EmailAlreadyExistsError(Exception):
        pass

    class UserNotFoundError(Exception):
        pass

    class _AuthStub:
        def create_user(self, **kwargs):  # pragma: no cover - not used in these tests
            return types.SimpleNamespace(uid="stub", email=kwargs.get("email"))

        def get_user_by_email(self, email):  # pragma: no cover
            return types.SimpleNamespace(uid="stub", email=email)

        def get_user(self, uid):  # pragma: no cover
            return types.SimpleNamespace(uid=uid, email=f"{uid}@example.com")
    # attach exception types as attributes
    _AuthStub.EmailAlreadyExistsError = EmailAlreadyExistsError
    _AuthStub.UserNotFoundError = UserNotFoundError

    class _CredentialsStub:
        class Certificate:
            def __init__(self, data):
                self.data = data

    firebase_admin = types.SimpleNamespace(
        initialize_app=lambda *a, **k: None,
        credentials=_CredentialsStub,
        auth=_AuthStub(),
        db=None,  # will be patched to FakeDB instance later
    )
    sys.modules.setdefault("firebase_admin", firebase_admin)
    sys.modules.setdefault("firebase_admin.auth", firebase_admin.auth)
    sys.modules.setdefault("firebase_admin.db", types.SimpleNamespace())
    sys.modules.setdefault("firebase_admin.credentials", _CredentialsStub)


# Install stubs before importing application modules
_install_firebase_stubs()

import os as _os  # noqa: E402
_BASE_DIR = _os.path.dirname(_os.path.dirname(__file__))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

import main as app_main  # noqa: E402
import routes as app_routes  # noqa: E402
import auth_routes as app_auth  # noqa: E402


class _Missing:
    pass


class FakeReference:
    def __init__(self, store: Dict[str, Any], path_parts: List[str]):
        self._store = store
        self._path = path_parts

    def _get_parent_and_key(self) -> Tuple[Dict[str, Any], str]:
        node = self._store
        for key in self._path[:-1]:
            node = node.setdefault(key, {})
        return node, self._path[-1] if self._path else ""

    def child(self, key: str) -> "FakeReference":
        return FakeReference(self._store, self._path + [key])

    def get(self) -> Any:
        node = self._store
        for key in self._path:
            if not isinstance(node, dict) or key not in node:
                return None
            node = node[key]
        return copy.deepcopy(node)

    def set(self, value: Any) -> None:
        if not self._path:
            raise ValueError("Cannot set root directly")
        parent, key = self._get_parent_and_key()
        parent[key] = copy.deepcopy(value)

    def update(self, value: Dict[str, Any]) -> None:
        current = self.get()
        if current is None:
            self.set(value)
            return
        if not isinstance(current, dict):
            raise ValueError("Can only update dict nodes")
        current.update(value)
        self.set(current)

    def delete(self) -> None:
        parent, key = self._get_parent_and_key()
        parent.pop(key, None)

    # Minimal no-op implementations to satisfy potential calls
    def order_by_child(self, _field: str) -> "FakeReference":
        return self

    def equal_to(self, _value: Any) -> "FakeReference":
        return self


class FakeDB:
    def __init__(self, initial: Optional[Dict[str, Any]] = None):
        self._store: Dict[str, Any] = initial or {}

    def reference(self, path: str) -> FakeReference:
        parts = [p for p in path.split("/") if p]
        return FakeReference(self._store, parts)


@pytest.fixture(autouse=True)
def patch_env():
    # Ensure AI endpoints don't fail on missing API key during tests
    old = os.environ.get("GOOGLE_AI_API_KEY")
    os.environ["GOOGLE_AI_API_KEY"] = "test-key"
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("GOOGLE_AI_API_KEY", None)
        else:
            os.environ["GOOGLE_AI_API_KEY"] = old


@pytest.fixture
def fake_db():
    initial = {
        "users": {},
        "restaurants": {},
        "menu_items": {},
    }
    return FakeDB(initial)


@pytest.fixture
def client(fake_db):
    # Patch db on both modules
    app_routes.db = fake_db  # type: ignore
    app_auth.db = fake_db  # type: ignore

    # Reset session tokens
    app_auth.SESSION_TOKENS.clear()

    # Seed two users in "users" path for admin checks
    users_ref = fake_db.reference("users")
    users_ref.child("user1").set({"is_admin": False, "email": "u1@example.com"})
    users_ref.child("admin1").set({"is_admin": True, "email": "admin@example.com"})

    # Seed tokens
    app_auth.SESSION_TOKENS["valid-user-token"] = {
        "uid": "user1",
        "email": "u1@example.com",
        "name": "User One",
        "is_admin": False,
    }
    app_auth.SESSION_TOKENS["valid-admin-token"] = {
        "uid": "admin1",
        "email": "admin@example.com",
        "name": "Admin One",
        "is_admin": True,
    }

    return TestClient(app_main.app)


@pytest.fixture
def user_auth_header():
    return {"Authorization": "Bearer valid-user-token"}


@pytest.fixture
def admin_auth_header():
    return {"Authorization": "Bearer valid-admin-token"}




