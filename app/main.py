from fastapi import FastAPI
from .auth import router as auth_router
from .expenses import router as expense_router
from .users import router as user
from .database import create_db
from fastapi.middleware.cors import CORSMiddleware
from .chat import router as chat


app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173",
                   "https://expense-tracker-frontend-nine-ruddy.vercel.app/"],
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