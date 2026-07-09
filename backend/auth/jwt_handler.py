"""Выпуск и разбор JWT-токенов доступа."""
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt

from database.config import get_settings


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(seconds=settings.JWT_EXPIRE_SECONDS),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
