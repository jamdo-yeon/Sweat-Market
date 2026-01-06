# Pydantic request schemas for form handling (optional but nice).
# TODO (A):
# - SignupForm(handle, password)
# - LoginForm(handle, password)
# TODO (B):
# - PostForm(title, body, tags)
# TODO (C):
# - OfferForm(title, when_text, where_text)

# app/schemas.py
from typing import Optional
from pydantic import BaseModel, Field, EmailStr

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    email: Optional[EmailStr] = None
    password: str = Field(min_length=6, max_length=128)

class UserLogin(BaseModel):
    username: str
    password: str

class ProfileUpdate(BaseModel):
    sport: Optional[str] = None
    time_window: Optional[str] = None
    region: Optional[str] = None
    goal: Optional[str] = None

class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    sport: Optional[str] = None
    time_window: Optional[str] = None
    region: Optional[str] = None
    goal: Optional[str] = None
