"""Зависимость FastAPI: извлекает и проверяет редактора из JWT-токена."""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from auth.jwt_handler import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def authenticate(token: str = Depends(oauth2_scheme)) -> int:
    """Возвращает id редактора из токена или отвечает 401."""
    payload = decode_access_token(token)
    if not payload or "user_id" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный или просроченный токен",
        )
    return payload["user_id"]
