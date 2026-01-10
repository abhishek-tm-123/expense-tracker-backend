from pydantic import BaseModel


class Register(BaseModel):
    name:str
    email:str
    password:str
    

class Login(BaseModel):
    email:str
    password:str
    
class UpdateProfile(BaseModel):
    name: str | None = None
    email: str | None = None

class ExpenseCreate(BaseModel):
    title:str
    amount:int
    category:str

class chatMessage(BaseModel):
    message: str

class chatHistoryMessage(BaseModel):
    user_id: int
    message: str
    sender: str  # 'user' or 'bot'

class BudgetCreate(BaseModel):
    category: str | None = None
    amount: float
    month: int
    year: int
    
class BudgetRead(BaseModel):
    budget_id: int
    category: str | None = None
    amount: float
    month: int
    year: int

class ChangePassword(BaseModel):
    old_password: str
    new_password: str
    