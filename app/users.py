from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from typing import Optional
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession as Session

from app.models import Users
from .auth import get_current_user
from .database import get_session
<<<<<<< HEAD

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
=======
from .schemas import UpdateProfile, ChangePassword
from .auth import pwd
>>>>>>> working-branch

router = APIRouter(prefix="/user")

@router.get("/me")
async def read_current_user(session:Session=Depends(get_session),current_user:int=Depends(get_current_user)):
    result = await session.execute(select(Users).where(Users.user_id == current_user))
    user = result.scalars().first()
    if not user:
        raise HTTPException(404,"User not found")
    return {"name": user.name, "email": user.email, "profile_image": user.profile_image}


@router.post("/change-password")
def change_password(
    data: ChangePassword,
    session: Session = Depends(get_session),
    current_user_id: int = Depends(get_current_user)
):
    user = session.exec(select(Users).where(Users.user_id == current_user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 1. Verify old password
    if not pwd.verify(data.old_password, user.password):
        raise HTTPException(status_code=400, detail="Current password incorrect")
    
    # 2. Update with new hashed password
    user.password = pwd.hash(data.new_password)
    
    session.add(user)
    session.commit()
    
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
        user.profile_image = upload_result.get("url")
        
<<<<<<< HEAD
    await session.commit()
    await session.refresh(user)
    return {"name": user.name, "email": user.email, "profile_image": user.profile_image}
=======
        # Generate unique filename to avoid collisions
        file_ext = os.path.splitext(profile_image.filename)[1]
        filename = f"{uuid4()}{file_ext}"
        file_path = f"app/static/profile_images/{filename}"
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(profile_image.file, buffer)
            
        # Store relative path or full URL. Here storing relative path served by static mount
        # Assuming domain is handled by frontend, or we can return full URL. 
        # Let's return the static path like /static/profile_images/...
        user.profile_image = f"/static/profile_images/{filename}"
        
    session.add(user)
    session.commit()
    session.refresh(user)
    return {"name": user.name, "email": user.email, "profile_image": user.profile_image}

@router.delete("/me")
def delete_current_user(
    session: Session = Depends(get_session),
    current_user_id: int = Depends(get_current_user)
):
    user = session.exec(select(Users).where(Users.user_id == current_user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 1. Delete profile image from disk if it exists
    if user.profile_image:
        import os
        # user.profile_image is like "/static/profile_images/uuid.ext"
        relative_path = user.profile_image.lstrip("/")
        if relative_path.startswith("static/"):
            physical_path = os.path.join("app", relative_path)
            if os.path.exists(physical_path):
                try:
                    os.remove(physical_path)
                except Exception as e:
                    print(f"Error deleting profile image: {e}")

    # 2. Delete user (cascading handles DB related data)
    session.delete(user)
    session.commit()
    
    return {"message": "Account and all associated data deleted successfully"}
>>>>>>> working-branch
