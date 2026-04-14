"""
Restaurant role and permission helpers for multi-user access.
Roles: manager (full control), staff (menu only).
"""
from typing import Optional, Any


def get_restaurant_role(db: Any, uid: str, restaurant_id: str, is_admin: bool) -> Optional[str]:
    """
    Return the user's role at this restaurant: "manager", "staff", or None.
    Global admins are treated as manager for access purposes.
    """
    if is_admin:
        return "manager"
    restaurant_ref = db.reference(f"restaurants/{restaurant_id}")
    restaurant_data = restaurant_ref.get()
    if not restaurant_data:
        return None
    if restaurant_data.get("owner_uid") == uid:
        return "manager"
    members_ref = db.reference(f"restaurant_members/{restaurant_id}")
    members = members_ref.get() or {}
    member_data = members.get(uid)
    if not member_data:
        return None
    return member_data.get("role")  # "manager" or "staff"


def can_manage_restaurant(db: Any, uid: str, restaurant_id: str, is_admin: bool) -> bool:
    """True if user can edit restaurant profile and manage team (manager or admin)."""
    return get_restaurant_role(db, uid, restaurant_id, is_admin) == "manager"


def can_edit_menu(db: Any, uid: str, restaurant_id: str, is_admin: bool) -> bool:
    """True if user can add/edit/delete menu items (manager, staff, or admin)."""
    role = get_restaurant_role(db, uid, restaurant_id, is_admin)
    return role in ("manager", "staff")
