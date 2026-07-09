"""API авторизации: регистрация и вход (выдача JWT)."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session

from auth.hash_password import hash_password, verify_password
from auth.jwt_handler import create_access_token
from database.database import get_session
from models.user import User
from schemas.auth import RegisterRequest, TokenResponse
from services.crud.user import create_user, get_user_by_username

auth_router = APIRouter(prefix="/auth", tags=["Авторизация"])


@auth_router.post("/register", status_code=201)
def register(data: RegisterRequest, session: Session = Depends(get_session)):
    if get_user_by_username(data.username, session):
        raise HTTPException(status_code=400, detail="Пользователь с таким именем уже существует")
    user = create_user(
        User(username=data.username, hashed_password=hash_password(data.password)),
        session,
    )
    return {"id": user.id, "username": user.username}


@auth_router.post("/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    user = get_user_by_username(form.username, session)
    if user is None or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")
    return TokenResponse(access_token=create_access_token(user.id))
