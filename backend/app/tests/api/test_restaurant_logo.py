"""Tests for the restaurant logo image storage lifecycle.

Covers the changes made under the "Restaurant logo upload" feature:
- Upload persists logo_path (DB source of truth) and returns a transient
  signed URL for immediate UI preview.
- Replace uploads delete the old blob best-effort.
- Delete clears logo_path and removes the blob.
- get_restaurant / get_restaurants regenerate fresh signed URLs from logo_path.
- AuthZ: managers/admins can change branding; staff cannot.
- Validation: non-image MIME types and oversize uploads are rejected.
"""

from fastapi.testclient import TestClient

import routes as app_routes


def _create_restaurant(client: TestClient, headers, name: str = "Logo Test") -> str:
    resp = client.post(
        "/restaurants/",
        headers=headers,
        json={
            "name": name,
            "phone": "+1 555 555 5555",
            "address": "123 Logo Lane",
            "cuisine_type": "Test",
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _upload_logo(
    client: TestClient,
    headers,
    restaurant_id: str,
    *,
    filename: str = "logo.png",
    content_type: str = "image/png",
    body: bytes = b"\x89PNGfake-png",
):
    return client.post(
        f"/api/restaurants/{restaurant_id}/logo",
        headers=headers,
        files={"file": (filename, body, content_type)},
    )


def test_upload_logo_persists_logo_path_only(
    client: TestClient, user_auth_header, fake_db, storage_objects
):
    restaurant_id = _create_restaurant(client, user_auth_header)

    resp = _upload_logo(client, user_auth_header, restaurant_id)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Response includes a transient signed URL plus the durable logo_path.
    assert body["logo_url"], "Response should include a signed URL for immediate UI preview"
    assert body["logo_path"].startswith(f"restaurants/{restaurant_id}/logo/")

    # Blob actually landed in (mock) storage with the correct content type.
    assert body["logo_path"] in storage_objects
    assert storage_objects[body["logo_path"]]["content_type"] == "image/png"

    # DB record stores logo_path as the durable source of truth; logo_url is
    # NOT persisted — it gets regenerated from logo_path on every GET.
    record = fake_db.reference(f"restaurants/{restaurant_id}").get()
    assert record["logo_path"] == body["logo_path"]
    assert "logo_url" not in record or record.get("logo_url") in (None, "")


def test_upload_logo_replace_deletes_old_blob(
    client: TestClient, user_auth_header, fake_db, storage_objects
):
    restaurant_id = _create_restaurant(client, user_auth_header)

    first = _upload_logo(client, user_auth_header, restaurant_id, body=b"first").json()
    second = _upload_logo(client, user_auth_header, restaurant_id, body=b"second").json()

    assert first["logo_path"] != second["logo_path"]
    # Old blob removed (best-effort cleanup), new blob present.
    assert first["logo_path"] not in storage_objects
    assert second["logo_path"] in storage_objects

    # DB record now points only at the latest blob.
    record = fake_db.reference(f"restaurants/{restaurant_id}").get()
    assert record["logo_path"] == second["logo_path"]


def test_upload_logo_replace_failure_to_delete_old_blob_does_not_break_upload(
    client: TestClient, user_auth_header, fake_db, storage_objects, monkeypatch
):
    """If the old blob cleanup raises, the upload should still succeed."""
    restaurant_id = _create_restaurant(client, user_auth_header)

    first = _upload_logo(client, user_auth_header, restaurant_id, body=b"first").json()
    assert first["logo_path"] in storage_objects

    def boom(self):  # pragma: no cover - exercised by patch
        raise RuntimeError("simulated storage failure")

    bucket_class = type(app_routes.storage.bucket())
    blob_class = type(bucket_class().blob("dummy"))
    monkeypatch.setattr(blob_class, "delete", boom)

    resp = _upload_logo(client, user_auth_header, restaurant_id, body=b"second")
    assert resp.status_code == 200, resp.text
    second = resp.json()
    assert second["logo_path"] in storage_objects
    # Old blob remains because deletion was sabotaged, but that's a leak we
    # accept — the user-visible upload still succeeds.
    assert first["logo_path"] in storage_objects


def test_upload_logo_rejects_non_image_mime(
    client: TestClient, user_auth_header, fake_db, storage_objects
):
    restaurant_id = _create_restaurant(client, user_auth_header)

    resp = _upload_logo(
        client,
        user_auth_header,
        restaurant_id,
        filename="logo.pdf",
        content_type="application/pdf",
        body=b"%PDF-1.4 fake",
    )
    assert resp.status_code == 400
    assert "JPEG" in resp.json().get("detail", "")
    # Nothing persisted to storage or DB.
    assert not storage_objects
    record = fake_db.reference(f"restaurants/{restaurant_id}").get()
    assert record.get("logo_path") in (None, "")


def test_upload_logo_rejects_oversize(
    client: TestClient, user_auth_header, fake_db, storage_objects
):
    restaurant_id = _create_restaurant(client, user_auth_header)

    oversize = b"x" * (app_routes.MAX_IMAGE_SIZE_BYTES + 1)
    resp = _upload_logo(client, user_auth_header, restaurant_id, body=oversize)
    assert resp.status_code == 400
    assert "5MB" in resp.json().get("detail", "")
    # Nothing persisted.
    assert not storage_objects
    record = fake_db.reference(f"restaurants/{restaurant_id}").get()
    assert record.get("logo_path") in (None, "")


def test_upload_logo_requires_auth(client: TestClient, user_auth_header, fake_db):
    restaurant_id = _create_restaurant(client, user_auth_header)
    resp = client.post(
        f"/api/restaurants/{restaurant_id}/logo",
        files={"file": ("logo.png", b"fake", "image/png")},
    )
    assert resp.status_code in (401, 403)


def test_upload_logo_staff_forbidden(
    client: TestClient, user_auth_header, staff_auth_header, fake_db, storage_objects
):
    """Staff (menu-editing access) cannot change restaurant branding."""
    restaurant_id = _create_restaurant(client, user_auth_header)
    # Add staff1 as staff for this restaurant
    fake_db.reference(f"restaurant_members/{restaurant_id}").set(
        {"staff1": {"role": "staff"}}
    )

    resp = _upload_logo(client, staff_auth_header, restaurant_id)
    assert resp.status_code == 403
    assert "manager" in resp.json().get("detail", "").lower()
    assert not storage_objects


def test_upload_logo_admin_allowed(
    client: TestClient, user_auth_header, admin_auth_header, fake_db, storage_objects
):
    """Global admins can update logos for any restaurant."""
    restaurant_id = _create_restaurant(client, user_auth_header)
    resp = _upload_logo(client, admin_auth_header, restaurant_id)
    assert resp.status_code == 200, resp.text


def test_delete_logo_clears_blob_and_db_field(
    client: TestClient, user_auth_header, fake_db, storage_objects
):
    restaurant_id = _create_restaurant(client, user_auth_header)
    upload = _upload_logo(client, user_auth_header, restaurant_id).json()
    assert upload["logo_path"] in storage_objects

    resp = client.delete(
        f"/api/restaurants/{restaurant_id}/logo",
        headers=user_auth_header,
    )
    assert resp.status_code == 200, resp.text

    # Blob deleted, logo_path cleared on the restaurant record, but the
    # restaurant itself still exists.
    assert upload["logo_path"] not in storage_objects
    record = fake_db.reference(f"restaurants/{restaurant_id}").get()
    assert record is not None
    assert record.get("logo_path") in (None, "")


def test_delete_logo_staff_forbidden(
    client: TestClient, user_auth_header, staff_auth_header, fake_db, storage_objects
):
    restaurant_id = _create_restaurant(client, user_auth_header)
    upload = _upload_logo(client, user_auth_header, restaurant_id).json()
    assert upload["logo_path"] in storage_objects

    fake_db.reference(f"restaurant_members/{restaurant_id}").set(
        {"staff1": {"role": "staff"}}
    )
    resp = client.delete(
        f"/api/restaurants/{restaurant_id}/logo",
        headers=staff_auth_header,
    )
    assert resp.status_code == 403
    # Blob must remain — staff didn't have permission.
    assert upload["logo_path"] in storage_objects


def test_delete_logo_when_none_exists(
    client: TestClient, user_auth_header, fake_db, storage_objects
):
    """Deleting a logo when none is set is still a no-op success."""
    restaurant_id = _create_restaurant(client, user_auth_header)
    resp = client.delete(
        f"/api/restaurants/{restaurant_id}/logo",
        headers=user_auth_header,
    )
    assert resp.status_code == 200, resp.text


def test_get_restaurant_attaches_fresh_signed_logo_url(
    client: TestClient, user_auth_header, fake_db, storage_objects
):
    restaurant_id = _create_restaurant(client, user_auth_header)
    upload = _upload_logo(client, user_auth_header, restaurant_id).json()

    # Manually clear any cached logo_url on the DB record (we don't persist
    # one, but the test is explicit about not relying on it) to prove the GET
    # endpoint regenerates a fresh signed URL from logo_path on every call.
    fake_db.reference(f"restaurants/{restaurant_id}").update({"logo_url": None})

    resp = client.get(f"/restaurants/{restaurant_id}", headers=user_auth_header)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["logo_path"] == upload["logo_path"]
    # The stub's signed URL is f"https://example.com/{path}", so the freshly
    # generated URL must contain the actual blob path.
    assert body["logo_url"]
    assert upload["logo_path"] in body["logo_url"]


def test_get_restaurants_attaches_fresh_signed_logo_url(
    client: TestClient, user_auth_header, fake_db, storage_objects
):
    restaurant_id = _create_restaurant(client, user_auth_header)
    upload = _upload_logo(client, user_auth_header, restaurant_id).json()

    resp = client.get("/restaurants", headers=user_auth_header)
    assert resp.status_code == 200, resp.text
    items = resp.json()
    matching = [r for r in items if r["id"] == restaurant_id]
    assert len(matching) == 1
    item = matching[0]
    assert item["logo_path"] == upload["logo_path"]
    assert item["logo_url"]
    assert upload["logo_path"] in item["logo_url"]


def test_get_restaurants_no_logo_url_when_no_path(
    client: TestClient, user_auth_header, fake_db, storage_objects
):
    """Restaurants without a logo should not get a fabricated logo_url."""
    restaurant_id = _create_restaurant(client, user_auth_header)
    resp = client.get("/restaurants", headers=user_auth_header)
    assert resp.status_code == 200, resp.text
    items = resp.json()
    matching = [r for r in items if r["id"] == restaurant_id]
    assert len(matching) == 1
    assert matching[0].get("logo_path") in (None, "")
    assert matching[0].get("logo_url") in (None, "")


def test_delete_restaurant_cleans_up_logo_blob(
    client: TestClient, user_auth_header, fake_db, storage_objects
):
    restaurant_id = _create_restaurant(client, user_auth_header)
    upload = _upload_logo(client, user_auth_header, restaurant_id).json()
    assert upload["logo_path"] in storage_objects

    resp = client.delete(
        f"/restaurants/{restaurant_id}",
        headers=user_auth_header,
    )
    assert resp.status_code == 200, resp.text

    # Restaurant DB record gone AND logo blob gone.
    assert fake_db.reference(f"restaurants/{restaurant_id}").get() is None
    assert upload["logo_path"] not in storage_objects
