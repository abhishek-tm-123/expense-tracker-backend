from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from typing import Optional
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession as Session

from app.models import Users
from .auth import get_current_user, pwd
from .database import get_session
from .schemas import ChangePassword

import cloudinary
import cloudinary.uploader
from fastapi.concurrency import run_in_threadpool
import os

cloudinary.config(
    cloud_name="dnkkkrerz",
    api_key="391655656674467",
    api_secret="bVtI8VxVqW4ZLLuZGlFBfycGujM",
    secure=True
)

router = APIRouter(prefix="/user")

@router.get("/me")
async def read_current_user(session:Session=Depends(get_session),current_user:int=Depends(get_current_user)):
    result = await session.execute(select(Users).where(Users.user_id == current_user))
    user = result.scalars().first()
    if not user:
        raise HTTPException(404,"User not found")
    return {
        "name": user.name, 
        "email": user.email, 
        "profile_image": user.profile_image,
        "has_onboarded": user.has_onboarded
    }


@router.post("/change-password")
async def change_password(
    data: ChangePassword,
    session: Session = Depends(get_session),
    current_user_id: int = Depends(get_current_user)
):
    result = await session.execute(select(Users).where(Users.user_id == current_user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 1. Verify old password
    if not pwd.verify(data.old_password, user.password):
        raise HTTPException(status_code=400, detail="Current password incorrect")
    
    # 2. Update with new hashed password
    user.password = pwd.hash(data.new_password)
    
    session.add(user)
    await session.commit()
    
    return {"message": "Password changed successfully"}


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
        user.profile_image = upload_result.get("secure_url")
        
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return {
        "name": user.name, 
        "email": user.email, 
        "profile_image": user.profile_image,
        "has_onboarded": user.has_onboarded
    }

@router.put("/onboarded")
async def set_onboarded(
    session: Session = Depends(get_session),
    current_user_id: int = Depends(get_current_user)
):
    result = await session.execute(select(Users).where(Users.user_id == current_user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.has_onboarded = True
    session.add(user)
    await session.commit()
    return {"message": "Onboarding status updated", "has_onboarded": True}

@router.delete("/me")
async def delete_current_user(
    session: Session = Depends(get_session),
    current_user_id: int = Depends(get_current_user)
):
    result = await session.execute(select(Users).where(Users.user_id == current_user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 1. Delete profile image from Cloudinary if it exists
    if user.profile_image:
        try:
            # Extract public_id from Cloudinary URL
            # URL format: https://res.cloudinary.com/{cloud_name}/image/upload/{version}/{public_id}.{format}
            # Example: https://res.cloudinary.com/dnkkkrerz/image/upload/v1234567890/profile_images/abc123.jpg
            # public_id would be: profile_images/abc123
            
            if "cloudinary.com" in user.profile_image:
                # Split URL and extract public_id
                parts = user.profile_image.split("/upload/")
                if len(parts) > 1:
                    # Get everything after /upload/, remove version if present
                    path_with_version = parts[1]
                    # Remove version (v1234567890/) if present
                    if path_with_version.startswith("v"):
                        path_parts = path_with_version.split("/", 1)
                        if len(path_parts) > 1:
                            public_id_with_ext = path_parts[1]
                        else:
                            public_id_with_ext = path_with_version
                    else:
                        public_id_with_ext = path_with_version
                    
                    # Remove file extension
                    public_id = os.path.splitext(public_id_with_ext)[0]
                    
                    # Delete from Cloudinary
                    await run_in_threadpool(cloudinary.uploader.destroy, public_id)
                    print(f"✓ Deleted image from Cloudinary: {public_id}")
        except Exception as e:
            print(f"⚠ Error deleting profile image from Cloudinary: {e}")

    # 2. Delete user (cascading handles DB related data)
    await session.delete(user)
    await session.commit()
    
    return {"message": "Account and all associated data deleted successfully"}
