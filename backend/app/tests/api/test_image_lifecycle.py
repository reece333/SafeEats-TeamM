"""Tests for the menu item image storage lifecycle.

Covers the changes made under the "Image storage and menu media" feature:
- Upload persists image_path (DB source of truth) and does NOT persist a
  long-lived image_url (signed URLs expire).
- Replace uploads delete the old blob best-effort.
- Duplicate clears BOTH image fields so duplicates don't share storage objects.
- Deleting a menu item also cleans up its blob.
- Menu list responses regenerate fresh signed URLs from image_path.
"""

from fastapi.testclient import TestClient

import routes as app_routes


def _create_restaurant(client: TestClient, headers) -> str:
    resp = client.post(
        "/restaurants/",
        headers=headers,
        json={
            "name": "Image Storage Test Restaurant",
            "phone": "+1 555 555 5555",
            "address": "123 Test Lane",
            "cuisine_type": "Test",
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _create_menu_item(client: TestClient, headers, restaurant_id: str, name: str = "Pasta") -> str:
    resp = client.post(
        f"/restaurants/{restaurant_id}/menu",
        headers=headers,
        json={
            "name": name,
            "description": f"{name} description",
            "price": 12.5,
            "ingredients": "noodles",
            "allergens": [],
            "dietaryCategories": [],
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _upload_image(
    client: TestClient,
    headers,
    menu_item_id: str,
    *,
    filename: str = "photo.jpg",
    content_type: str = "image/jpeg",
    body: bytes = b"\xff\xd8\xff\xe0fake-jpeg",
):
    return client.post(
        "/api/upload-image",
        headers=headers,
        files={"file": (filename, body, content_type)},
        data={"menu_item_id": menu_item_id},
    )


def test_upload_persists_image_path_only(
    client: TestClient, user_auth_header, fake_db, storage_objects
):
    restaurant_id = _create_restaurant(client, user_auth_header)
    menu_item_id = _create_menu_item(client, user_auth_header, restaurant_id)

    resp = _upload_image(client, user_auth_header, menu_item_id)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Response includes a transient signed URL plus the durable image_path.
    assert body["image_url"], "Response should include a signed URL for immediate UI preview"
    assert body["image_path"].startswith(f"menu_items/{menu_item_id}/")

    # Blob actually landed in (mock) storage with the correct content type.
    assert body["image_path"] in storage_objects
    assert storage_objects[body["image_path"]]["content_type"] == "image/jpeg"

    # DB record stores image_path as source of truth and explicitly does NOT
    # persist image_url long-term (because signed URLs expire).
    record = fake_db.reference(f"menu_items/{menu_item_id}").get()
    assert record["image_path"] == body["image_path"]
    assert record.get("image_url") in (None, "")


def test_upload_replace_deletes_old_blob(
    client: TestClient, user_auth_header, fake_db, storage_objects
):
    restaurant_id = _create_restaurant(client, user_auth_header)
    menu_item_id = _create_menu_item(client, user_auth_header, restaurant_id)

    first = _upload_image(client, user_auth_header, menu_item_id, body=b"first").json()
    second = _upload_image(client, user_auth_header, menu_item_id, body=b"second").json()

    assert first["image_path"] != second["image_path"]
    # Old blob removed (best-effort cleanup), new blob present.
    assert first["image_path"] not in storage_objects
    assert second["image_path"] in storage_objects

    # DB record now points only at the latest blob.
    record = fake_db.reference(f"menu_items/{menu_item_id}").get()
    assert record["image_path"] == second["image_path"]


def test_upload_replace_failure_to_delete_old_blob_does_not_break_upload(
    client: TestClient, user_auth_header, fake_db, storage_objects, monkeypatch
):
    """If the old blob cleanup raises, the upload should still succeed."""
    restaurant_id = _create_restaurant(client, user_auth_header)
    menu_item_id = _create_menu_item(client, user_auth_header, restaurant_id)

    first = _upload_image(client, user_auth_header, menu_item_id, body=b"first").json()
    assert first["image_path"] in storage_objects

    # Sabotage delete() so the cleanup throws — the new upload must still land.
    def boom(self):  # pragma: no cover - exercised by patch
        raise RuntimeError("simulated storage failure")

    bucket_class = type(app_routes.storage.bucket())
    blob_class = type(bucket_class().blob("dummy"))
    monkeypatch.setattr(blob_class, "delete", boom)

    resp = _upload_image(client, user_auth_header, menu_item_id, body=b"second")
    assert resp.status_code == 200, resp.text
    second = resp.json()
    assert second["image_path"] in storage_objects
    # Old blob remains because deletion was sabotaged, but that's a leak we
    # accept — the user-visible upload still succeeds.
    assert first["image_path"] in storage_objects


def test_delete_menu_item_cleans_up_blob(
    client: TestClient, user_auth_header, fake_db, storage_objects
):
    restaurant_id = _create_restaurant(client, user_auth_header)
    menu_item_id = _create_menu_item(client, user_auth_header, restaurant_id)
    upload = _upload_image(client, user_auth_header, menu_item_id).json()
    assert upload["image_path"] in storage_objects

    resp = client.delete(
        f"/restaurants/{restaurant_id}/menu/{menu_item_id}",
        headers=user_auth_header,
    )
    assert resp.status_code == 200, resp.text

    # DB record gone AND blob gone.
    assert fake_db.reference(f"menu_items/{menu_item_id}").get() is None
    assert upload["image_path"] not in storage_objects


def test_delete_menu_item_without_image_does_not_error(
    client: TestClient, user_auth_header, fake_db, storage_objects
):
    """A menu item that never had an image should still delete cleanly."""
    restaurant_id = _create_restaurant(client, user_auth_header)
    menu_item_id = _create_menu_item(client, user_auth_header, restaurant_id)

    resp = client.delete(
        f"/restaurants/{restaurant_id}/menu/{menu_item_id}",
        headers=user_auth_header,
    )
    assert resp.status_code == 200, resp.text
    assert fake_db.reference(f"menu_items/{menu_item_id}").get() is None


def test_duplicate_does_not_inherit_image(
    client: TestClient, user_auth_header, fake_db, storage_objects
):
    restaurant_id = _create_restaurant(client, user_auth_header)
    original_id = _create_menu_item(client, user_auth_header, restaurant_id, name="Original")
    upload = _upload_image(client, user_auth_header, original_id).json()
    assert upload["image_path"] in storage_objects

    resp = client.post(
        f"/restaurants/{restaurant_id}/menu/{original_id}/duplicate",
        headers=user_auth_header,
    )
    assert resp.status_code == 200, resp.text
    duplicate = resp.json()

    # Duplicate gets a fresh id, no image fields, and the original blob is
    # untouched (i.e. the duplicate doesn't reference the same storage object).
    assert duplicate["id"] != original_id
    assert duplicate.get("image_path") in (None, "")
    assert duplicate.get("image_url") in (None, "")

    duplicate_record = fake_db.reference(f"menu_items/{duplicate['id']}").get()
    assert duplicate_record.get("image_path") in (None, "")
    assert duplicate_record.get("image_url") in (None, "")

    original_record = fake_db.reference(f"menu_items/{original_id}").get()
    assert original_record["image_path"] == upload["image_path"]
    assert upload["image_path"] in storage_objects


def test_delete_image_endpoint_clears_blob_and_db_fields(
    client: TestClient, user_auth_header, fake_db, storage_objects
):
    restaurant_id = _create_restaurant(client, user_auth_header)
    menu_item_id = _create_menu_item(client, user_auth_header, restaurant_id)
    upload = _upload_image(client, user_auth_header, menu_item_id).json()
    assert upload["image_path"] in storage_objects

    resp = client.delete(
        f"/api/delete-image/{menu_item_id}",
        headers=user_auth_header,
    )
    assert resp.status_code == 200, resp.text

    # Blob deleted, both fields cleared on the menu item record, but the
    # menu item itself still exists.
    assert upload["image_path"] not in storage_objects
    record = fake_db.reference(f"menu_items/{menu_item_id}").get()
    assert record is not None
    assert record.get("image_path") in (None, "")
    assert record.get("image_url") in (None, "")


def test_menu_list_attaches_fresh_signed_urls_from_image_path(
    client: TestClient, user_auth_header, fake_db, storage_objects
):
    restaurant_id = _create_restaurant(client, user_auth_header)
    menu_item_id = _create_menu_item(client, user_auth_header, restaurant_id)
    upload = _upload_image(client, user_auth_header, menu_item_id).json()

    # Manually clear the response-time image_url on the DB record to prove
    # the menu list endpoint regenerates it from image_path on every fetch
    # (this is the "refresh" mechanism the frontend relies on).
    fake_db.reference(f"menu_items/{menu_item_id}").update({"image_url": None})

    resp = client.get(
        f"/restaurants/{restaurant_id}/menu",
        headers=user_auth_header,
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert len(items) == 1
    item = items[0]
    assert item["image_path"] == upload["image_path"]
    # The stub's signed URL is f"https://example.com/{path}", so it must
    # contain the actual blob path — i.e. it was generated fresh, not stale.
    assert item["image_url"]
    assert upload["image_path"] in item["image_url"]


def test_menu_list_no_image_url_for_items_without_image_path(
    client: TestClient, user_auth_header, fake_db, storage_objects
):
    """Items without an image should not get a fabricated image_url."""
    restaurant_id = _create_restaurant(client, user_auth_header)
    _create_menu_item(client, user_auth_header, restaurant_id, name="No Image")

    resp = client.get(
        f"/restaurants/{restaurant_id}/menu",
        headers=user_auth_header,
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert len(items) == 1
    assert items[0].get("image_path") in (None, "")
    assert items[0].get("image_url") in (None, "")
