"""Схемы регистрации и выдачи токена."""
from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    # Требования к учётке проверяются на сервере: витрина — не единственный вход (есть и API).
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
