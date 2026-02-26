from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from .budget import router as budget_router
from .auth import router as auth_router
from .expenses import router as expense_router
from .users import router as user
from .database import create_db
from fastapi.middleware.cors import CORSMiddleware
from .chat import router as chat
from .dashboard import router as dashboard_router
from starlette.middleware.base import BaseHTTPMiddleware





# Force reload change
import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

app = FastAPI()

# --- GLOBAL EXCEPTION HANDLER ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log the error (in production, use a proper logger)
    print(f"ERROR: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "An internal server error occurred.",
            "details": str(exc) if os.getenv("DEBUG_MODE", "false").lower() == "true" else None
        },
    )

# --- SECURE HEADERS MIDDLEWARE ---
class SecureHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(SecureHeadersMiddleware)




import os

origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,https://expense-tracker-frontend-nine-ruddy.vercel.app")
origins = [origin.strip() for origin in origins_str.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
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