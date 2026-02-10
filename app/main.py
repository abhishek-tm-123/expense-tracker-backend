from fastapi import FastAPI
from .budget import router as budget_router
from .auth import router as auth_router
from .expenses import router as expense_router
from .users import router as user
from .database import create_db
from fastapi.middleware.cors import CORSMiddleware
from .chat import router as chat
from .dashboard import router as dashboard_router





import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

app = FastAPI()




import os

origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,https://expense-tracker-frontend-nine-ruddy.vercel.app")
origins = [origin.strip() for origin in origins_str.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.on_event("startup")
async def on_startup():
    await create_db()

@app.get("/test")
def test():
    return {"hello":"world"}


app.include_router(auth_router)
app.include_router(expense_router)
app.include_router(user)
app.include_router(chat)
app.include_router(dashboard_router)
app.include_router(budget_router)