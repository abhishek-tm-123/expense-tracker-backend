from fastapi import FastAPI
from .auth import router as auth_router
from .database import create_db

app = FastAPI()
@app.on_event("startup")
def on_startup():
    create_db()

@app.get("/test")
def test():
    return {"hello":"world"}


app.include_router(auth_router)