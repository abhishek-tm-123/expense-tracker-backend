from datetime import datetime, timedelta
# from dateutil.relativedelta import relativedelta # Avoid dependency
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession as Session
import logging

from ..models import Expense, Budget, ChatHistory, Income
from ..utils.entity_extractor import get_professional_response

# Helper for month calculation
def add_months(sourcedate, months):
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(sourcedate.day, [31,
        29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
        31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month-1])
    return sourcedate.replace(year=year, month=month, day=day)


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
    # 1. Determine Date Range & Context
    start_date = entities.get("start_date")
    end_date = entities.get("end_date")
    range_label = entities.get("date_label")
    category = entities.get("category")
    
    period_type = "week" # Default tracking

    # Determine requested period type from label
    target_period = None
    if range_label:
        if "month" in range_label:
             target_period = "month"
        elif "week" in range_label:
             target_period = "week"
    
    # Handle Contextual Navigation (Next/Previous)
    if range_label and ("next" in range_label or "previous" in range_label):
        # Fetch last bot message with expense context
        stmt = select(ChatHistory).where(
            ChatHistory.user_id == user_id,
            ChatHistory.sender == 'bot'
        ).order_by(ChatHistory.timestamp.desc()).limit(10)
        
        result = await session.execute(stmt)
        history = result.scalars().all()
        
        last_context = None
        for msg in history:
            if msg.data and isinstance(msg.data, dict) and "start_date" in msg.data and "period_type" in msg.data:
                last_context = msg.data
                break
        
        if last_context:
            try:
                prev_start = datetime.strptime(last_context["start_date"], "%Y-%m-%d")
                prev_period = last_context.get("period_type", "week")
                
                # If user explicitly requested a period, use it; otherwise use previous
                period_type = target_period if target_period else prev_period
                
                if "next" in range_label:
                    if period_type == "week":
                        if prev_period == "month":
                             # Reset to today's next week? Or start of next month?
                             # Let's align to start of next week from *prev_start* (which was month start)
                             start_date = prev_start + timedelta(days=7) # simplified
                        else:
                             start_date = prev_start + timedelta(days=7)
                             
                        end_date = start_date + timedelta(days=6)
                        range_label = f"week of {start_date.strftime('%d %b')}"
                    elif period_type == "month":
                        start_date = add_months(prev_start, 1)
                        # Ensure we are at start of month
                        start_date = start_date.replace(day=1)
                        end_date = add_months(start_date, 1) - timedelta(days=1)
                        range_label = start_date.strftime("%B %Y")
                        
                elif "previous" in range_label:
                    if period_type == "week":
                        start_date = prev_start - timedelta(days=7)
                        end_date = start_date + timedelta(days=6)
                        range_label = f"week of {start_date.strftime('%d %b')}"
                    elif period_type == "month":
                        start_date = add_months(prev_start, -1)
                        start_date = start_date.replace(day=1)
                        end_date = add_months(start_date, 1) - timedelta(days=1)
                        range_label = start_date.strftime("%B %Y")
            except Exception as e:
                logger.error(f"Error parsing context dates: {e}")
                pass

    # Default logic (No context or explicit current period)
    if not start_date or not end_date:
        today = datetime.now()
        
        # If explicit instruction "monthly" (target_period="month") but no next/prev
        if target_period == "month":
             period_type = "month"
        elif target_period == "week":
             period_type = "week"
        # Else default to week (already set)
        
        if period_type == "week":
            start_day = today - timedelta(days=today.weekday()) # Mon
            start_date = start_day.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = (start_day + timedelta(days=6)).replace(hour=23, minute=59, second=59)
            range_label = "this week"
        elif period_type == "month": 
            start_date = today.replace(day=1, hour=0, minute=0, second=0)
            end_date = add_months(start_date, 1) - timedelta(days=1)
            end_date = end_date.replace(hour=23, minute=59, second=59)
            range_label = "this month"

    # Ensure datetime objects for query
    if isinstance(start_date, (datetime,)):
         pass # Already datetime
    else:
        # If passed as something else (unlikely with current flow but safe)
        pass 

    # 2. Query Expenses
    stmt = select(Expense).where(Expense.user_id == user_id)
    stmt = stmt.where(Expense.created_at >= start_date, Expense.created_at <= end_date)
    
    if category:
        stmt = stmt.where(Expense.category == category)
    
    stmt = stmt.order_by(Expense.created_at.asc())
    
    result = await session.execute(stmt)
    expenses = result.scalars().all()
    
    # Serialize expenses for the frontend table
    expenses_data = [
        {"id": e.exp_id, "title": e.title, "amount": e.amount, "category": e.category, "date": e.created_at.strftime("%Y-%m-%d")}
        for e in expenses
    ]
    
    # 3. Construct Response
    total = sum(e.amount for e in expenses)
    period_str = range_label if range_label else f"{start_date.strftime('%d %b')} - {end_date.strftime('%d %b')}"
    
    if not expenses:
        base_msg = f"📂 **No expenses found** for {period_str}. You're clear!"
    else:
        header = f"📝 **Expenses for {period_str}**"
        if category:
            header = f"📝 **{category.title()} Expenses ({period_str})**"
        
        # We don't list all text rows if there are too many, frontend handles table.
        # But we provide a summary text.
        base_msg = f"{header}\nTotal: **₹{total}**"

    # Interactive Prompt
    prompt = "\n\nWould you like to see expenses for the **previous week**, **next week**, or switch to **monthly** view?"
    
    final_message = base_msg + prompt

    # 4. Return Context Data
    response_data = {
        "expenses": expenses_data,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "period_type": period_type,
        "total": total
    }
    
    return final_message, response_data

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

async def handle_add_income(entities, user_id, session: Session):
    if not entities["amount"]:
        return get_professional_response("add_income", entities, success=False), False
        
    now = datetime.now()
    month, year = now.month, now.year
    
    # Logic: Only one income per user per month
    stmt = select(Income).where(
        Income.user_id == user_id,
        Income.month == month,
        Income.year == year
    )
    result = await session.execute(stmt)
    existing_income = result.scalars().first()
    
    updated = False
    if existing_income:
        existing_income.amount = entities["amount"]
        updated = True
        logger.info(f"Updated income for user {user_id}: {entities['amount']} for {month}/{year}")
    else:
        new_income = Income(
            user_id=user_id,
            amount=entities["amount"],
            month=month,
            year=year
        )
        session.add(new_income)
        logger.info(f"Saved new income for user {user_id}: {entities['amount']} for {month}/{year}")
    
    await session.commit()
    return get_professional_response("add_income", entities, success=True, data={"updated": updated, "month": month, "year": year}), True
