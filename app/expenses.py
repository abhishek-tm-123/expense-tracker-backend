from fastapi import APIRouter,Depends,HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession as Session

from .auth import get_current_user
from .database import get_session
from .schemas import ExpenseCreate
from .models import Expense

router = APIRouter(prefix="/expenses")


@router.post("/create")
async def create_expense(data:ExpenseCreate,session:Session=Depends(get_session),current_user:int=Depends(get_current_user)):

    expense = Expense(
        user_id=current_user,
        title=data.title,
        amount=data.amount,
        category=data.category
    )
    session.add(expense)
    await session.commit()

    
    return {"messege":"Expense created"}

@router.get("/get")
async def get_allexpenses(session:Session=Depends(get_session),current_user:int=Depends(get_current_user)):
    user_id = current_user
    result = await session.execute(select(Expense).where(Expense.user_id == user_id))
    expenses = result.scalars().all()
    return expenses

@router.get("/get/{expense_id}")
async def get_expense(expense_id:int,session:Session=Depends(get_session),current_user:int=Depends(get_current_user)):
    result = await session.execute(
        select(Expense).where(Expense.exp_id == expense_id, Expense.user_id == current_user)
    )
    expense = result.scalars().first()
    if not expense:
        raise HTTPException(404, "Expense not found or unauthorized")
    return expense

@router.put("/edit/{expense_id}")
async def edit_expenses(
    expense_id:int,
    data:ExpenseCreate,
    session:Session = Depends(get_session),
    current_user:int=Depends(get_current_user)
):
    result = await session.execute(
        select(Expense).where(Expense.exp_id==expense_id, Expense.user_id == current_user)
    )
    expense = result.scalars().first()

    if not expense:
        raise HTTPException(404,"Expense not found or unauthorized")
    
    # Update fields
    expense.title = data.title
    expense.amount = data.amount
    expense.category = data.category

    session.add(expense)
    await session.commit()
    await session.refresh(expense)
    return {"message": "Expense updated", "expense": expense}


@router.delete("/dlt/{expense_id}")
async def delete_expense(
    expense_id: int,
    session: Session = Depends(get_session),
    current_user: int = Depends(get_current_user)
):
    result = await session.execute(
        select(Expense).where(Expense.exp_id == expense_id, Expense.user_id == current_user)
    )

    expense = result.scalars().first()

    if not expense:
        raise HTTPException(404, "Expense not found or unauthorized")

    session.delete(expense)
    await session.commit()

    return {"message": "Expense deleted"}


