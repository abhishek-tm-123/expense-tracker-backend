from fastapi import FastAPI
from .budget import router as budget_router
from .auth import router as auth_router
from .expenses import router as expense_router
from .users import router as user
from .database import create_db
from fastapi.middleware.cors import CORSMiddleware
from .chat import router as chat
from .dashboard import router as dashboard_router


from fastapi.staticfiles import StaticFiles
import os

app = FastAPI()

# Ensure static directory exists
os.makedirs("app/static/profile_images", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.on_event("startup")
def on_startup():
    create_db()

@app.get("/test")
def test():
    return {"hello":"world"}


app.include_router(auth_router)
app.include_router(expense_router)
app.include_router(user)
app.include_router(chat)
app.include_router(dashboard_router)
app.include_router(budget_router)