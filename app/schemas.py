from pydantic import BaseModel, EmailStr, Field

class Register(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)

class Login(BaseModel):
    email: EmailStr
    password: str

class UpdateProfile(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    email: EmailStr | None = None

class ExpenseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    amount: float = Field(..., gt=0, le=100000000)
    category: str = Field(..., min_length=1, max_length=50)

class chatMessage(BaseModel):
    message: str = Field(..., max_length=500)

class chatHistoryMessage(BaseModel):
    user_id: int
    message: str
    sender: str  # 'user' or 'bot'

class BudgetCreate(BaseModel):
    category: str | None = Field(None, min_length=1, max_length=50)
    amount: float = Field(..., gt=0, le=100000000)
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2000, le=2100)

class BudgetRead(BaseModel):
    budget_id: int
    category: str | None = None
    amount: float
    month: int
    year: int

class ChangePassword(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)
    