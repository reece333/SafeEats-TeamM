from fastapi import APIRouter, HTTPException, Depends, Request, status
from pydantic import BaseModel
from typing import Optional, List
import firebase_admin
from firebase_admin import auth
import json
import time
import secrets  # For generating session tokens

from permissions import get_restaurant_role, can_manage_restaurant

def _db():
    return firebase_admin.db

auth_router = APIRouter()

# Store session tokens in memory (for simplicity)
# In production, you should use Redis or a database
SESSION_TOKENS = {}

class UserRegister(BaseModel):
    email: str
    password: str
    name: Optional[str] = None
    restaurantName: Optional[str] = None
    is_admin: Optional[bool] = False

class LoginData(BaseModel):
    email: str
    password: str
    
class MakeAdminData(BaseModel):
    email: str

class UserResponse(BaseModel):
    uid: str
    email: str
    token: str
    name: Optional[str] = None
    restaurantId: Optional[str] = None
    is_admin: bool = False
    restaurants: Optional[List[dict]] = None  # [{ id, name, role }]


class InviteMemberData(BaseModel):
    email: str
    role: str  # "manager" | "staff"

class UserListItem(BaseModel):
    uid: str
    email: str
    name: Optional[str] = None
    is_admin: bool = False
    restaurant_name: Optional[str] = None
    created_at: Optional[int] = None

# Middleware to verify token
async def verify_token(request: Request):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header"
        )
    
    token = auth_header.split('Bearer ')[1]
    
    # Check if token exists in our session store
    if token in SESSION_TOKENS:
        return SESSION_TOKENS[token]
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

# Admin-only middleware
async def admin_only(request: Request):
    token_data = await verify_token(request)
    
    # Check if user is an admin
    if not token_data.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return token_data


def _get_user_restaurants_with_roles(uid: str, is_admin: bool) -> tuple:
    """
    Return (restaurant_id_for_default, list of { id, name, role }).
    restaurant_id is first restaurant for backward compat; restaurants list has role for UI.
    """
    all_restaurants = _db().reference("restaurants").get() or {}
    members_by_restaurant = _db().reference("restaurant_members").get() or {}
    result = []
    for r_id, r_data in all_restaurants.items():
        role = None
        if r_data.get("owner_uid") == uid:
            role = "manager"
        elif r_id in members_by_restaurant and uid in members_by_restaurant[r_id]:
            role = members_by_restaurant[r_id][uid].get("role")  # "manager" or "staff"
        if is_admin or role:
            result.append({
                "id": str(r_id),
                "name": r_data.get("name", "Unnamed Restaurant"),
                "role": role if role else "manager",
            })
    default_id = result[0]["id"] if result else None
    return default_id, result

@auth_router.post("/register", response_model=UserResponse)
async def register_user(user_data: UserRegister):
    """Register a new user with Firebase Auth"""
    try:
        # Create user in Firebase Auth
        user_record = auth.create_user(
            email=user_data.email,
            password=user_data.password,
            display_name=user_data.name
        )
        
        # Generate a session token
        session_token = secrets.token_hex(32)
        
        # Determine if user should be admin
        is_admin = user_data.is_admin
        
        # Save session data with admin status and name
        SESSION_TOKENS[session_token] = {
            "uid": user_record.uid,
            "email": user_record.email,
            "name": user_data.name,
            "is_admin": is_admin
        }
        
        # Save additional user data
        user_ref = _db().reference(f'users/{user_record.uid}')
        user_ref.set({
            "email": user_data.email,
            "name": user_data.name,
            "restaurantName": user_data.restaurantName,
            "is_admin": is_admin,
            "created_at": int(time.time())
        })
        
        restaurant_id, restaurants = _get_user_restaurants_with_roles(user_record.uid, is_admin)
        
        return {
            "uid": user_record.uid,
            "email": user_record.email,
            "token": session_token,
            "name": user_data.name,
            "restaurantId": restaurant_id,
            "is_admin": is_admin,
            "restaurants": restaurants,
        }
    except auth.EmailAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration error: {str(e)}"
        )

@auth_router.post("/login", response_model=UserResponse)
async def login_user(login_data: LoginData):
    """Login an existing user"""
    try:
        # Firebase Admin SDK doesn't provide direct email/password signin
        # We need to find the user by email first
        user = auth.get_user_by_email(login_data.email)
        
        # Get user data to check admin status and get name
        user_ref = _db().reference(f'users/{user.uid}')
        user_data = user_ref.get()
        is_admin = user_data.get('is_admin', False) if user_data else False
        name = user_data.get('name') if user_data else user.display_name
        
        # Generate a session token
        session_token = secrets.token_hex(32)
        
        # Store session data with admin status and name
        SESSION_TOKENS[session_token] = {
            "uid": user.uid,
            "email": user.email,
            "name": name,
            "is_admin": is_admin
        }
        
        restaurant_id, restaurants = _get_user_restaurants_with_roles(user.uid, is_admin)
        
        return {
            "uid": user.uid,
            "email": user.email,
            "token": session_token,
            "name": name,
            "restaurantId": restaurant_id,
            "is_admin": is_admin,
            "restaurants": restaurants,
        }
    except auth.UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login error: {str(e)}"
        )

@auth_router.get("/user")
async def get_current_user(token_data: dict = Depends(verify_token)):
    """Get current user information"""
    try:
        uid = token_data["uid"]
        
        # Get user data from Firebase Auth
        user = auth.get_user(uid)
        
        # Get user data from Realtime Database to include admin status and name
        user_ref = _db().reference(f'users/{uid}')
        user_data = user_ref.get()
        is_admin = user_data.get('is_admin', False) if user_data else False
        name = user_data.get('name') if user_data else user.display_name
        
        restaurant_id, restaurants = _get_user_restaurants_with_roles(uid, is_admin)
        
        return {
            "uid": uid,
            "email": user.email,
            "name": name,
            "restaurantId": restaurant_id,
            "is_admin": is_admin,
            "restaurants": restaurants,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting user: {str(e)}"
        )


# --- Restaurant team (manager-only) ---

@auth_router.get("/restaurants/{restaurant_id}/members")
async def get_restaurant_members(restaurant_id: str, token_data: dict = Depends(verify_token)):
    """List members of a restaurant. Manager or admin only."""
    uid = token_data.get("uid")
    is_admin = token_data.get("is_admin", False)
    if not can_manage_restaurant(_db(), uid, restaurant_id, is_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manager access required")
    restaurant_ref = _db().reference(f"restaurants/{restaurant_id}")
    if not restaurant_ref.get():
        raise HTTPException(status_code=404, detail="Restaurant not found")
    members_ref = _db().reference(f"restaurant_members/{restaurant_id}")
    members = members_ref.get() or {}
    restaurant_data = restaurant_ref.get()
    owner_uid = restaurant_data.get("owner_uid")
    out = []
    if owner_uid:
        try:
            owner = auth.get_user(owner_uid)
            out.append({"uid": owner_uid, "email": owner.email, "role": "manager", "is_owner": True})
        except Exception:
            out.append({"uid": owner_uid, "email": "?", "role": "manager", "is_owner": True})
    for member_uid, data in members.items():
        if member_uid == owner_uid:
            continue
        try:
            u = auth.get_user(member_uid)
            out.append({"uid": member_uid, "email": u.email, "role": data.get("role", "staff"), "is_owner": False})
        except Exception:
            out.append({"uid": member_uid, "email": "?", "role": data.get("role", "staff"), "is_owner": False})
    return {"members": out}


@auth_router.post("/restaurants/{restaurant_id}/members")
async def invite_restaurant_member(restaurant_id: str, body: InviteMemberData, token_data: dict = Depends(verify_token)):
    """Invite a user by email to the restaurant. Manager or admin only."""
    if body.role not in ("manager", "staff"):
        raise HTTPException(status_code=400, detail="role must be 'manager' or 'staff'")
    uid = token_data.get("uid")
    is_admin = token_data.get("is_admin", False)
    if not can_manage_restaurant(_db(), uid, restaurant_id, is_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manager access required")
    restaurant_ref = _db().reference(f"restaurants/{restaurant_id}")
    if not restaurant_ref.get():
        raise HTTPException(status_code=404, detail="Restaurant not found")
    try:
        user = auth.get_user_by_email(body.email)
    except auth.UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found with that email")
    member_uid = user.uid
    members_ref = _db().reference(f"restaurant_members/{restaurant_id}")
    members = members_ref.get() or {}
    if member_uid in members:
        raise HTTPException(status_code=400, detail="User is already a member")
    restaurant_data = restaurant_ref.get()
    if restaurant_data.get("owner_uid") == member_uid:
        raise HTTPException(status_code=400, detail="Owner is already a member")
    members[member_uid] = {"role": body.role}
    members_ref.set(members)
    return {"message": f"Added {body.email} as {body.role}"}


@auth_router.delete("/restaurants/{restaurant_id}/members/{member_uid}")
async def remove_restaurant_member(restaurant_id: str, member_uid: str, token_data: dict = Depends(verify_token)):
    """Remove a member. Manager or admin only. Cannot remove owner."""
    uid = token_data.get("uid")
    is_admin = token_data.get("is_admin", False)
    if not can_manage_restaurant(_db(), uid, restaurant_id, is_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manager access required")
    restaurant_ref = _db().reference(f"restaurants/{restaurant_id}")
    restaurant_data = restaurant_ref.get()
    if not restaurant_data:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    if restaurant_data.get("owner_uid") == member_uid:
        raise HTTPException(status_code=400, detail="Cannot remove the restaurant owner")
    members_ref = _db().reference(f"restaurant_members/{restaurant_id}")
    members = members_ref.get() or {}
    if member_uid not in members:
        raise HTTPException(status_code=404, detail="Member not found")
    del members[member_uid]
    members_ref.set(members)
    return {"message": "Member removed"}


# Add a method to get all users (admin-only)
@auth_router.get("/users", response_model=List[UserListItem])
async def get_all_users(token_data: dict = Depends(admin_only)):
    """Get all users (admin only)"""
    try:
        # Get all users from database
        users_ref = _db().reference('users')
        all_users = users_ref.get()
        
        if not all_users:
            return []
        
        # Get all restaurants for lookup
        restaurant_ref = _db().reference('restaurants')
        all_restaurants = restaurant_ref.get() or {}
        
        # Build restaurant mapping (owner uid -> restaurant name)
        restaurant_map = {}
        for r_id, r_data in all_restaurants.items():
            owner_uid = r_data.get('owner_uid')
            if owner_uid:
                restaurant_map[owner_uid] = r_data.get('name', 'Unnamed Restaurant')
        
        # Format user data for response
        user_list = []
        for uid, user_data in all_users.items():
            # Get additional user info from Firebase Auth if needed
            try:
                auth_user = auth.get_user(uid)
                email = auth_user.email
            except:
                # Fallback to stored email if Firebase Auth lookup fails
                email = user_data.get('email', 'Unknown')
            
            restaurant_name = restaurant_map.get(uid)
            
            user_list.append({
                "uid": uid,
                "email": email,
                "name": user_data.get('name'),
                "is_admin": user_data.get('is_admin', False),
                "restaurant_name": restaurant_name,
                "created_at": user_data.get('created_at')
            })
        
        # Sort by creation date (newest first)
        user_list.sort(key=lambda x: x.get('created_at', 0) or 0, reverse=True)
        
        return user_list
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting users: {str(e)}"
        )

# Add a method to make a user an admin by email (admin-only access)
@auth_router.post("/make-admin-by-email")
async def make_user_admin_by_email(admin_data: MakeAdminData, token_data: dict = Depends(admin_only)):
    """Make a user an admin by email (requires admin privileges)"""
    try:
        # Get user by email
        user = auth.get_user_by_email(admin_data.email)
        
        # Update user record in database
        user_ref = _db().reference(f'users/{user.uid}')
        user_ref.update({
            "is_admin": True
        })
        
        # Update session token if the user is currently logged in
        for token, data in list(SESSION_TOKENS.items()):
            if data.get("email") == admin_data.email:
                SESSION_TOKENS[token]["is_admin"] = True
        
        return {"message": f"User {admin_data.email} is now an admin"}
    except auth.UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating user: {str(e)}"
        )

# Add a method to make a user an admin (admin-only access)
@auth_router.post("/make-admin/{user_id}")
async def make_user_admin(user_id: str, token_data: dict = Depends(admin_only)):
    """Make a user an admin (requires admin privileges)"""
    try:
        # Get user data to verify they exist
        user = auth.get_user(user_id)
        
        # Update user record in database
        user_ref = _db().reference(f'users/{user_id}')
        user_ref.update({
            "is_admin": True
        })
        
        # Update session token if the user is currently logged in
        for token, data in list(SESSION_TOKENS.items()):
            if data.get("uid") == user_id:
                SESSION_TOKENS[token]["is_admin"] = True
        
        return {"message": f"User {user.email} is now an admin"}
    except auth.UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating user: {str(e)}"
        )
        
# Add a logout endpoint
@auth_router.post("/logout")
async def logout_user(token_data: dict = Depends(verify_token)):
    """Logout a user by invalidating their token"""
    try:
        # Get the token from the authorization header
        auth_header = token_data.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split('Bearer ')[1]
            
            # Remove the token from the session store
            if token in SESSION_TOKENS:
                del SESSION_TOKENS[token]
                
        return {"message": "Logged out successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Logout error: {str(e)}"
        )
    
@auth_router.post("/remove-admin-by-email")
async def remove_user_admin_by_email(admin_data: MakeAdminData, token_data: dict = Depends(admin_only)):
    """Remove admin privileges from a user by email (requires admin privileges)"""
    try:
        # First check that user is not removing their own admin privileges
        if admin_data.email == token_data.get("email"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot remove your own admin privileges"
            )
            
        # Get user by email
        user = auth.get_user_by_email(admin_data.email)
        
        # Update user record in database
        user_ref = _db().reference(f'users/{user.uid}')
        user_ref.update({
            "is_admin": False
        })
        
        # Update session token if the user is currently logged in
        for token, data in list(SESSION_TOKENS.items()):
            if data.get("email") == admin_data.email:
                SESSION_TOKENS[token]["is_admin"] = False
        
        return {"message": f"Admin privileges removed from user {admin_data.email}"}
    except auth.UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating user: {str(e)}"
        )