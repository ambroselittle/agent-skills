from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from src.database import get_session
from src.models import User, UserCreate, UserPublic, UserUpdate

router = APIRouter()


@router.post("/", response_model=UserPublic)
def create_user(*, session: Session = Depends(get_session), user: UserCreate) -> User:
    db_user = User.model_validate(user)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


@router.get("/", response_model=list[UserPublic])
def list_users(
    *,
    session: Session = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
) -> list[User]:
    return session.exec(select(User).offset(offset).limit(limit)).all()


@router.get("/{user_id}", response_model=UserPublic)
def get_user(*, session: Session = Depends(get_session), user_id: int) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=UserPublic)
def update_user(
    *, session: Session = Depends(get_session), user_id: int, user: UserUpdate
) -> User:
    db_user = session.get(User, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    user_data = user.model_dump(exclude_unset=True)
    db_user.sqlmodel_update(user_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


@router.delete("/{user_id}")
def delete_user(*, session: Session = Depends(get_session), user_id: int) -> dict:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    session.delete(user)
    session.commit()
    return {"ok": True}
