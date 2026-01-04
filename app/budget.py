from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from .auth import get_current_user
from .database import get_session
from .schemas import BudgetCreate,BudgetRead
from .models import Budget, Expense



router = APIRouter(prefix="/budget")

@router.post("/", response_model=BudgetRead)
def create_or_update_budget(
    data: BudgetCreate,
    session: Session = Depends(get_session),
    current_user: int = Depends(get_current_user),
):
    statement = select(Budget).where(
        Budget.user_id == current_user,
        Budget.category == data.category,
        Budget.month == data.month,
        Budget.year == data.year,
    )

    budget = session.exec(statement).first()

    if budget:
        budget.amount = data.amount
    else:
        budget = Budget(
            user_id=current_user,
            category=data.category,
            amount=data.amount,
            month=data.month,
            year=data.year,
        )
        session.add(budget)

    session.commit()
    session.refresh(budget)

    return {"message": "Budget created/updated successfully", "budget": budget}
