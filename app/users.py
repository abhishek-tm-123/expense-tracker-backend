from fastapi import APIRouter,Depends,HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession as Session

from app.models import Users
from .auth import get_current_user
from .database import get_session

router = APIRouter(prefix="/user")

@router.get("/me")
async def read_current_user(session:Session=Depends(get_session),current_user:int=Depends(get_current_user)):
    result = await session.execute(select(Users).where(Users.user_id == current_user))
    user = result.scalars().first()
    if not user:
        raise HTTPException(404,"User not found")
    return {"name": user.name, "email": user.email}