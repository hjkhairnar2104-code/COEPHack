from pydantic import BaseModel, EmailStr
from typing import Optional
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    BILLING_SPECIALIST = "billing_specialist"
    BENEFITS_ADMIN = "benefits_admin"

class User(BaseModel):
    id: Optional[str] = None  # MongoDB _id as string
    email: EmailStr
    hashed_password: str
    role: UserRole
    active: bool = True