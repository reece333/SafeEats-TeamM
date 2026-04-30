from fastapi import APIRouter, HTTPException, Depends, Request, status
from pydantic import BaseModel
from typing import Optional, List
from firebase_admin import auth, db
import json
import time
import secrets  # For generating session tokens

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
        user_ref = db.reference(f'users/{user_record.uid}')
        user_ref.set({
            "email": user_data.email,
            "name": user_data.name,
            "restaurantName": user_data.restaurantName,
            "is_admin": is_admin,
            "created_at": int(time.time())
        })

        # Try to find existing restaurant for this user
        restaurant_ref = db.reference('restaurants')
        restaurants = restaurant_ref.order_by_child(
            'owner_uid').equal_to(user_record.uid).get()

        restaurant_id = None
        if restaurants:
            restaurant_id = list(restaurants.keys())[0]

        return {
            "uid": user_record.uid,
            "email": user_record.email,
            "token": session_token,
            "name": user_data.name,
            "restaurantId": restaurant_id,
            "is_admin": is_admin
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
        user_ref = db.reference(f'users/{user.uid}')
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

        # Get restaurant ID if exists
        restaurant_ref = db.reference('restaurants')
        restaurants = restaurant_ref.order_by_child(
            'owner_uid').equal_to(user.uid).get()

        restaurant_id = None
        if restaurants:
            restaurant_id = list(restaurants.keys())[0]

        return {
            "uid": user.uid,
            "email": user.email,
            "token": session_token,
            "name": name,
            "restaurantId": restaurant_id,
            "is_admin": is_admin
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
        user_ref = db.reference(f'users/{uid}')
        user_data = user_ref.get()
        is_admin = user_data.get('is_admin', False) if user_data else False
        name = user_data.get('name') if user_data else user.display_name

        # Get restaurant ID if exists
        restaurant_ref = db.reference('restaurants')
        restaurants = restaurant_ref.order_by_child(
            'owner_uid').equal_to(uid).get()

        restaurant_id = None
        if restaurants:
            restaurant_id = list(restaurants.keys())[0]

        return {
            "uid": uid,
            "email": user.email,
            "name": name,
            "restaurantId": restaurant_id,
            "is_admin": is_admin
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting user: {str(e)}"
        )

# Add a method to get all users (admin-only)


@auth_router.get("/users", response_model=List[UserListItem])
async def get_all_users(token_data: dict = Depends(admin_only)):
    """Get all users (admin only)"""
    try:
        # Get all users from database
        users_ref = db.reference('users')
        all_users = users_ref.get()

        if not all_users:
            return []

        # Get all restaurants for lookup
        restaurant_ref = db.reference('restaurants')
        all_restaurants = restaurant_ref.get() or {}

        # Build restaurant mapping (owner uid -> restaurant name)
        restaurant_map = {}
        for r_id, r_data in all_restaurants.items():
            owner_uid = r_data.get('owner_uid')
            if owner_uid:
                restaurant_map[owner_uid] = r_data.get(
                    'name', 'Unnamed Restaurant')

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
        user_ref = db.reference(f'users/{user.uid}')
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
        user_ref = db.reference(f'users/{user_id}')
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
        user_ref = db.reference(f'users/{user.uid}')
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
