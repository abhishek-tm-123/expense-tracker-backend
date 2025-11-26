from sqlmodel import SQLModel,Field
from typing import Optional
from datetime import datetime

class Users(SQLModel,table=True):
    id: Optional[int] = Field(default=None,primary_key=True)
    name:str
    email:str=Field(index=True,unique=True)
    password:str
