from datetime import datetime
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession as Session
import logging

from ..models import Expense, Budget, ChatHistory
from ..utils.entity_extractor import get_professional_response

# Configure Logger
logger = logging.getLogger(__name__)

async def save_chat_history(user_id:int, message:str, sender:str, session:Session, data:dict=None):   
    chat_entry = ChatHistory(user_id=user_id, message=message, sender=sender, data=data)
    session.add(chat_entry)
    await session.commit()
    return chat_entry

async def handle_add_expense(entities, user_id, session: Session):
    if not entities["amount"] or not entities["category"]:
        return get_professional_response("add_expense", entities, success=False), False
    
    expense = Expense(
        title=f"{entities['category'].title()} expense",
        user_id=user_id,
        amount=entities["amount"],
        category=entities["category"]
    )
    session.add(expense)
    
    # --- BUDGET WARNING LOGIC ---
    now = datetime.now()
    month, year = now.month, now.year
    
    start_of_month = datetime(year, month, 1)
    
    # Check total spent
    stmt_spent = select(Expense).where(
        Expense.user_id == user_id,
        Expense.created_at >= start_of_month
    )
    result = await session.execute(stmt_spent)
    all_expenses = result.scalars().all()
    total_spent = sum(e.amount for e in all_expenses)
    
    cat_spent = sum(e.amount for e in all_expenses if e.category == entities["category"])
    
    warning = None
    stmt_budgets = select(Budget).where(
        Budget.user_id == user_id, 
        Budget.month == month, 
        Budget.year == year
    )
    result_budgets = await session.execute(stmt_budgets)
    budgets = result_budgets.scalars().all()
    
    for b in budgets:
        if b.category == entities["category"]:
            if cat_spent > b.amount:
                warning = f"Budget for {b.category.title()} exceeded! (₹{cat_spent}/₹{b.amount})"
            elif cat_spent > b.amount * 0.9:
                warning = f"Approaching {b.category.title()} budget limit. (₹{cat_spent}/₹{b.amount})"
        
        if b.category is None:
            if total_spent > b.amount:
                warning = f"Overall monthly budget exceeded! (₹{total_spent}/₹{b.amount})"
            elif total_spent > b.amount * 0.9:
                warning = f"Approaching overall monthly budget limit. (₹{total_spent}/₹{b.amount})"

    await session.commit()
    logger.info(f"Expense added for user {user_id}: {entities['amount']} on {entities['category']}")
    return get_professional_response("add_expense", entities, success=True, warning=warning), True

async def handle_total_expenses(entities, user_id, session: Session):
    stmt = select(Expense).where(Expense.user_id == user_id)
    if entities["start_date"] and entities["end_date"]:
        stmt = stmt.where(Expense.created_at >= entities["start_date"], Expense.created_at <= entities["end_date"])
    
    if entities["category"]:
        stmt = stmt.where(Expense.category == entities["category"])
    
    result = await session.execute(stmt)
    expenses = result.scalars().all()
    total = sum(e.amount for e in expenses)
    return get_professional_response("total_expenses", entities, data={"total": total})

async def handle_show_expenses(entities, user_id, session: Session):
    stmt = select(Expense).where(Expense.user_id == user_id)
    if entities["start_date"] and entities["end_date"]:
        stmt = stmt.where(Expense.created_at >= entities["start_date"], Expense.created_at <= entities["end_date"])
    
    if entities["category"]:
        stmt = stmt.where(Expense.category == entities["category"])
    
    stmt = stmt.order_by(Expense.created_at.asc())
    
    result = await session.execute(stmt)
    expenses = result.scalars().all()
    
    # Serialize expenses for the frontend table
    expenses_data = [
        {"id": e.exp_id, "title": e.title, "amount": e.amount, "category": e.category, "date": e.created_at.strftime("%Y-%m-%d")}
        for e in expenses
    ]
    
    return get_professional_response("show_expenses", entities, data={"expenses": expenses}), expenses_data

async def handle_set_budget(entities, user_id, session: Session):
    if not entities["amount"]:
        return get_professional_response("set_budget", entities, success=False), False
    
    now = datetime.now()
    month, year = now.month, now.year
    
    stmt = select(Budget).where(
        Budget.user_id == user_id,
        Budget.category == entities["category"],
        Budget.month == month,
        Budget.year == year
    )
    result = await session.execute(stmt)
    existing_budget = result.scalars().first()
    
    if existing_budget:
        existing_budget.amount = entities["amount"]
        logger.info(f"Updated budget for user {user_id}: {entities['category']} -> {entities['amount']}")
    else:
        budget = Budget(
            user_id=user_id,
            category=entities["category"],
            amount=entities["amount"],
            month=month,
            year=year
        )
        session.add(budget)
        logger.info(f"Created budget for user {user_id}: {entities['category']} -> {entities['amount']}")
    
    await session.commit()
    return get_professional_response("set_budget", entities, success=True), True

async def handle_show_budget(entities, user_id, session: Session):
    now = datetime.now()
    month, year = now.month, now.year
    
    stmt = select(Budget).where(
        Budget.user_id == user_id,
        Budget.month == month,
        Budget.year == year
    )
    result = await session.execute(stmt)
    budgets = result.scalars().all()
    
    if not budgets:
        return get_professional_response("show_budget", entities, data={"budgets": []})
    
    start_of_month = datetime(year, month, 1)
    stmt_expenses = select(Expense).where(
        Expense.user_id == user_id,
        Expense.created_at >= start_of_month
    )
    result_expenses = await session.execute(stmt_expenses)
    expenses = result_expenses.scalars().all()
    
    spent_map = {}
    for e in expenses:
        spent_map[e.category] = spent_map.get(e.category, 0) + e.amount
    
    spent_map[None] = sum(e.amount for e in expenses)
    
    # Serialize budget data for the frontend table
    budget_data = []
    for b in budgets:
        cat = b.category.title() if b.category else "Overall"
        spent = spent_map.get(b.category, 0)
        percent = (spent / b.amount) * 100 if b.amount > 0 else 0
        budget_data.append({
            "category": cat,
            "spent": spent,
            "limit": b.amount,
            "percent": f"{percent:.1f}%"
        })
    
    return get_professional_response("show_budget", entities, data={"budgets": budgets, "spent_map": spent_map}), budget_data
