from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime


class Users(SQLModel, table=True):
    user_id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str = Field(index=True, unique=True)
    password: str
    profile_image: Optional[str] = Field(default=None)
   
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


class Expense(SQLModel, table=True):
    exp_id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    amount: float
    created_at: datetime = Field(default_factory=datetime.utcnow)
    category:str
    user_id: int = Field(foreign_key="users.user_id", ondelete="CASCADE")

    user: Optional[Users] = Relationship(back_populates="expenses")

class ChatHistory(SQLModel, table=True):
    chat_id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.user_id", ondelete="CASCADE")
    message: str
    sender: str  # 'user' or 'bot'
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