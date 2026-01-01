from pydantic import BaseModel


class Register(BaseModel):
    name:str
    email:str
    password:str
    

class Login(BaseModel):
    email:str
    password:str

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
    