from pydantic import BaseModel
from typing import List, Optional

class Restaurant(BaseModel):
    name: str
    address: str
    phone: str
    cuisine_type: str

class MenuItem(BaseModel):
    name: str
    description: str
    price: float
    ingredients: str = ""
    allergens: List[str] = [] 
    dietaryCategories: List[str] = [] 
    archived: bool = False


class MenuItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    ingredients: Optional[str] = None
    allergens: Optional[List[str]] = None
    dietaryCategories: Optional[List[str]] = None
    archived: Optional[bool] = None


class BulkMenuUpdate(BaseModel):
    item_ids: List[str]
    add_allergens: List[str] = []
    remove_allergens: List[str] = []
    add_dietary_categories: List[str] = []
    remove_dietary_categories: List[str] = []

class UserCreate(BaseModel):
    email: str
    password: str
    display_name: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    uid: str
    email: str
    display_name: Optional[str] = None