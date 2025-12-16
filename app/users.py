from fastapi import APIRouter,Depends,HTTPException
from sqlmodel import Session,select

from app.models import Users
from .auth import get_current_user
from .database import get_session

router = APIRouter(prefix="/user")

@router.get("/me")
def read_current_user(session:Session=Depends(get_session),current_user:int=Depends(get_current_user)):
    user = session.exec(select(Users).where(Users.user_id == current_user)).first()
    if not user:
        raise HTTPException(404,"User not found")
    return {"name": user.name, "email": user.email}