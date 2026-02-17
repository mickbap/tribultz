from uuid import UUID
from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenPayload(BaseModel):
    sub: str  # user_id (UUID string)
    tenant_id: str
    role: str
    exp: int
    iat: int


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    tenant_slug: str = "default"


class UserRead(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    role: str
    tenant_id: UUID
    is_active: bool

    class Config:
        from_attributes = True
