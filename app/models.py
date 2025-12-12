from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime


class Users(SQLModel, table=True):
    user_id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str = Field(index=True, unique=True)
    password: str
    account_type:str
    expenses: List["Expense"] = Relationship(back_populates="user")


class Expense(SQLModel, table=True):
    exp_id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    amount: float
    created_at: datetime = Field(default_factory=datetime.utcnow)
    category:str
    user_id: int = Field(foreign_key="users.user_id")  # FK MUST match table name + column

    user: Optional[Users] = Relationship(back_populates="expenses")
