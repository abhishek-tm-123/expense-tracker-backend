from fastapi import APIRouter,HTTPException,Header,Depends,Request,Response
from passlib.context import CryptContext
from sqlmodel import Session,select
from jose import jwt,JWTError
from datetime import datetime,timedelta
import os



from .schemas import Register,Login
from .database import get_session
from .models import Users



router = APIRouter(prefix="/auth")
pwd = CryptContext(schemes=["argon2"],deprecated="auto")

SECRET = os.getenv("SECRET_KEY")
ALGO = "HS256"

def create_token(data:dict,expires_minutes:int):
    to_encode = data.copy()
    expire = datetime.utcnow()+timedelta(minutes=expires_minutes)
    to_encode.update({"exp":expire})
    return jwt.encode(to_encode,SECRET,ALGO)

def get_current_user(authorization: str = Header(None)):
    if authorization is None:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    try:
        scheme, token = authorization.split()  # Expect "Bearer <token>"
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid auth scheme")
        payload = jwt.decode(token, SECRET, algorithms=[ALGO])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return int(user_id)
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")

@router.post("/register")
def register(user:Register,session:Session = Depends(get_session)):
    exists = session.exec(select(Users).where(Users.email == user.email)).first()
    if exists:
        raise HTTPException(409,"Email already exists")
    new_user = Users(email=user.email,password=pwd.hash(user.password),name=user.name)
    session.add(new_user)
    session.commit()
    return {"message" : "User created"}

@router.post("/login")
def login(user: Login,response:Response,session:Session=Depends(get_session)):
    db_user = session.exec(select(Users).where(Users.email == user.email)).first()
    if not db_user or not pwd.verify(user.password,db_user.password):
        raise HTTPException(401,"Invalid credentials")
    access = create_token({"sub":str(db_user.user_id)},2)
    refresh = create_token({"sub":str(db_user.user_id)},60*24*7)  # 7 days
    # Set refresh token in secure httpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh,
        httponly=True,
        secure=False,     # set True when using HTTPS
        samesite="lax",
        path="/",
        max_age=60*60*24*7  # 7 days
    )
    return {"access_token": access}

@router.post("/refresh")
def refresh_token(request: Request, session: Session = Depends(get_session)):
    print(f"DEBUG: Cookies keys received: {request.cookies.keys()}")
    refresh_token = request.cookies.get("refresh_token")
    
    if not refresh_token:
        print("DEBUG: Refresh token cookie is MISSING")
        raise HTTPException(401, "Refresh token missing")

    try:
        payload = jwt.decode(refresh_token, SECRET, algorithms=[ALGO])
        user_id = payload.get("sub")
        
        if user_id is None:
             print("DEBUG: Token payload invalid (no sub)")
             raise HTTPException(401, "Invalid token payload")

        # Verify user exists in DB
        user = session.get(Users, int(user_id))
        if not user:
            print(f"DEBUG: User {user_id} not found in DB")
            raise HTTPException(401, "User no longer exists")

        new_access = create_token({"sub": str(user_id)}, 2)
        print("DEBUG: Token refreshed successfully")

        return {"access_token": new_access}

    except JWTError as e:
        print(f"DEBUG: JWT Error: {str(e)}")
        if "Signature has expired" in str(e):
            raise HTTPException(401, "Refresh token expired")
        raise HTTPException(401, "Invalid refresh token")




