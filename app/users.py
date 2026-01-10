from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from typing import Optional
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession as Session

from app.models import Users
from .auth import get_current_user
from .database import get_session

import cloudinary
import cloudinary.uploader
from fastapi.concurrency import run_in_threadpool
import os

cloudinary.config(
    cloud_name="dnkkkrerz",
    api_key="391655656674467",
    api_secret="**********",
    secure=True
)

router = APIRouter(prefix="/user")

@router.get("/me")
async def read_current_user(session:Session=Depends(get_session),current_user:int=Depends(get_current_user)):
    result = await session.execute(select(Users).where(Users.user_id == current_user))
    user = result.scalars().first()
    if not user:
        raise HTTPException(404,"User not found")
    return {"name": user.name, "email": user.email, "profile_image": user.profile_image}

@router.put("/profile")
async def update_profile(
    name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    profile_image: Optional[UploadFile] = File(None),
    session: Session = Depends(get_session),
    current_user_id: int = Depends(get_current_user)
):
    result = await session.execute(select(Users).where(Users.user_id == current_user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if name is not None:
        user.name = name
        
    if email is not None and email != user.email:
        result = await session.execute(select(Users).where(Users.email == email))
        existing_user = result.scalars().first()
        if existing_user:
            raise HTTPException(status_code=409, detail="Email already in use")
        user.email = email
    
    if profile_image:
        # 1. Upload to Cloudinary using run_in_threadpool (since SDK is blocking)
        # We pass profile_image.file directly to the uploader
        upload_result = await run_in_threadpool(
            cloudinary.uploader.upload, 
            profile_image.file,
            folder="profile_images" # Organizes your Cloudinary media library
        )
        user.profile_image = upload_result.get("url")
        
    await session.commit()
    await session.refresh(user)
    return {"name": user.name, "email": user.email, "profile_image": user.profile_image}