from fastapi import APIRouter,Depends,HTTPException, File, UploadFile, Form
from typing import Optional
from sqlmodel import Session,select

from app.models import Users
from .auth import get_current_user
from .database import get_session
from .schemas import UpdateProfile

router = APIRouter(prefix="/user")

@router.get("/me")
def read_current_user(session:Session=Depends(get_session),current_user:int=Depends(get_current_user)):
    user = session.exec(select(Users).where(Users.user_id == current_user)).first()
    if not user:
        raise HTTPException(404,"User not found")
    return {"name": user.name, "email": user.email, "profile_image": user.profile_image}

@router.put("/profile")
def update_profile(
    name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    profile_image: Optional[UploadFile] = File(None),
    session: Session = Depends(get_session),
    current_user_id: int = Depends(get_current_user)
):
    user = session.exec(select(Users).where(Users.user_id == current_user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if name is not None:
        user.name = name
        
    if email is not None and email != user.email:
        existing_user = session.exec(select(Users).where(Users.email == email)).first()
        if existing_user:
            raise HTTPException(status_code=409, detail="Email already in use")
        user.email = email
    
    if profile_image:
        import shutil
        import os
        from uuid import uuid4
        
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