from fastapi import APIRouter,Depends,HTTPException
from sqlmodel import Session,select


from .auth import get_current_user
from .database import get_session
from .schemas import ExpenseCreate
from .models import Expense

router = APIRouter(prefix="/expenses")


@router.post("/create")
def create_expense(data:ExpenseCreate,session:Session=Depends(get_session),current_user:int=Depends(get_current_user)):

    expense = Expense(
        user_id=current_user,
        title=data.title,
        amount=data.amount,
        category=data.category
    )
    session.add(expense)
    session.commit()

    
    return {"messege":"Expense created"}

@router.get("/get")
def get_allexpenses(session:Session=Depends(get_session),current_user:int=Depends(get_current_user)):
    user_id = current_user
    expenses = session.exec(select(Expense).where(Expense.user_id == user_id)).all()
    return expenses

@router.get("/get/{expense_id}")
def get_expense(expense_id:int,session:Session=Depends(get_session),current_user:int=Depends(get_current_user)):
    expense = session.exec(select(Expense).where(Expense.exp_id == expense_id)).first()
    return expense

@router.put("/edit/{expense_id}")
def edit_expenses(
    expense_id:int,
    data:ExpenseCreate,
    session:Session = Depends(get_session),
    current_user:int=Depends(get_current_user)
):
    expense = session.exec(
        select(Expense).where(Expense.exp_id==expense_id)
    ).first()

    if not expense:
        raise HTTPException(404,"Expense not found")
    
    if expense.user_id != current_user:
        raise HTTPException(403,"you cannot edit this expense")
    # Update fields
    expense.title = data.title
    expense.amount = data.amount
    expense.category = data.category

    session.add(expense)
    session.commit()
    session.refresh(expense)
    return {"message": "Expense updated", "expense": expense}


@router.delete("/dlt/{expense_id}")
def delete_expense(
    expense_id: int,
    session: Session = Depends(get_session),
    current_user: int = Depends(get_current_user)
):
    expense = session.exec(
        select(Expense).where(Expense.exp_id == expense_id)
    ).first()

    if not expense:
        raise HTTPException(404, "Expense not found")

    if expense.user_id != current_user:
        raise HTTPException(403, "You cannot delete this expense")

    session.delete(expense)
    session.commit()

    return {"message": "Expense deleted"}


