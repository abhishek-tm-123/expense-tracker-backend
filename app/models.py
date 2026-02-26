from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, Dict
from datetime import datetime
from sqlalchemy import JSON, Column


class Users(SQLModel, table=True):
    user_id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str = Field(index=True, unique=True)
    password: str
    is_admin: bool = Field(default=False)
    profile_image: Optional[str] = Field(default=None)
    has_onboarded: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
   
    # Cascading deletions: when a user is deleted, all their data goes too
    expenses: List["Expense"] = Relationship(
        back_populates="user", 
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    budgets: List["Budget"] = Relationship(
        back_populates="user", 
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    chat_history: List["ChatHistory"] = Relationship(
        back_populates="user", 
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    incomes: List["Income"] = Relationship(
        back_populates="user", 
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class Expense(SQLModel, table=True):
    exp_id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    amount: float
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    category:str = Field(index=True)
    user_id: int = Field(foreign_key="users.user_id", ondelete="CASCADE", index=True)

    user: Optional[Users] = Relationship(back_populates="expenses")

class ChatHistory(SQLModel, table=True):
    chat_id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.user_id", ondelete="CASCADE")
    message: str
    sender: str  # 'user' or 'bot'
    data: Optional[Dict] = Field(default=None, sa_column=Column(JSON))
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    user: Optional[Users] = Relationship(back_populates="chat_history")

class Budget(SQLModel, table=True):
    budget_id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.user_id", ondelete="CASCADE")
    category: Optional[str]  = Field(default=None, index=True)
    amount: float = Field(gt=0)
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2000)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    user: Optional[Users] = Relationship(back_populates="budgets")

class Income(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.user_id", ondelete="CASCADE")
    amount: float = Field(gt=0)
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2000)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    user: Optional[Users] = Relationship(back_populates="incomes")