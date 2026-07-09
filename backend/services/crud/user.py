"""CRUD учётных записей редакторов."""
from typing import Optional

from sqlmodel import Session, select

from models.user import User


def create_user(user: User, session: Session) -> User:
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_user(user_id: int, session: Session) -> Optional[User]:
    return session.get(User, user_id)


def get_user_by_username(username: str, session: Session) -> Optional[User]:
    return session.exec(select(User).where(User.username == username)).first()
