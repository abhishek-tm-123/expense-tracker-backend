from pydantic import BaseModel


class Register(BaseModel):
    name:str
    email:str
    password:str
    account_type:str

class Login(BaseModel):
    email:str
    password:str

class ExpenseCreate(BaseModel):
    title:str
    amount:int
    category:str
    