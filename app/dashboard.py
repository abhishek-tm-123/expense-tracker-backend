from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession as Session
from datetime import datetime, timedelta, time

from .auth import get_current_user
from .database import get_session
from .models import Expense, Budget

router = APIRouter(prefix="/dashboard")

def get_date_range(range: str, start_date_str: str = None, end_date_str: str = None):
    today = datetime.utcnow().date()

    if range == "week":
        start_date = today - timedelta(days=7)
        end_date = today
    elif range == "month":
        start_date = today.replace(day=1)
        end_date = today
    elif range == "custom":
        if not start_date_str or not end_date_str:
            raise HTTPException(400, "Custom range requires start_date and end_date (YYYY-MM-DD)")
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD")
    else:
        raise HTTPException(400, "Invalid range. Use 'week', 'month', 'custom'")

    start_dt = datetime.combine(start_date, time.min)   # 00:00:00
    end_dt   = datetime.combine(end_date, time.max)        # 23:59:59.999999

    return start_dt, end_dt


@router.get("")
async def get_dashboard(
    range: str,
    start_date: str = None,
    end_date: str = None,
    session: Session = Depends(get_session),
    current_user: int = Depends(get_current_user)
):
    start_dt, end_dt = get_date_range(range, start_date, end_date)
    
    # Current period expenses
    result = await session.execute(
        select(Expense).where(
            Expense.user_id == current_user,
            Expense.created_at >= start_dt,
            Expense.created_at <= end_dt
        )
    )
    expenses = result.scalars().all()

    # Previous period expenses for changePercent
    period_days = (end_dt - start_dt).days + 1
    prev_start_date = start_dt - timedelta(days=period_days)
    prev_end_date = start_dt - timedelta(seconds=1)
    
    prev_result = await session.execute(
        select(Expense).where(
            Expense.user_id == current_user,
            Expense.created_at >= prev_start_date,
            Expense.created_at <= prev_end_date
        )
    )
    prev_expenses = prev_result.scalars().all()
    
    prev_total = sum(e.amount for e in prev_expenses)
    current_total = sum(e.amount for e in expenses)
    
    if prev_total > 0:
        change_percent = round(((current_total - prev_total) / prev_total) * 100, 1)
    else:
        change_percent = 100.0 if current_total > 0 else 0.0

    # Budget Logic (Monthly based)
    now = datetime.utcnow()
    month, year = now.month, now.year
    start_of_month = datetime(year, month, 1)
    
    # 1. Fetch all monthly expenses for budget checking
    monthly_result = await session.execute(
        select(Expense).where(
            Expense.user_id == current_user,
            Expense.created_at >= start_of_month
        )
    )
    monthly_expenses = monthly_result.scalars().all()
    monthly_total = sum(e.amount for e in monthly_expenses)
    
    # 2. Fetch budgets
    budgets_result = await session.execute(
        select(Budget).where(
            Budget.user_id == current_user,
            Budget.month == month,
            Budget.year == year
        )
    )
    budgets = budgets_result.scalars().all()

    return build_dashboard_response(expenses, monthly_expenses, budgets, start_dt, end_dt, change_percent)

def build_dashboard_response(expenses, monthly_expenses, budgets, start_dt, end_dt, change_percent):
    total_expense = sum(exp.amount for exp in expenses)
    days_count = max((end_dt - start_dt).days, 1)
    avg_daily = round(total_expense / days_count, 2) if days_count > 0 else 0
    
    category_map = {}
    
    # Pre-fill daily map with all days in range to avoid gaps
    daily_map = {}
    current_day = start_dt.date()
    while current_day <= end_dt.date():
        daily_map[current_day.strftime("%d %b")] = 0
        current_day += timedelta(days=1)

    for e in expenses:  
        category_map[e.category] = category_map.get(e.category, 0) + e.amount
        day_str = e.created_at.strftime("%d %b")
        if day_str in daily_map:
            daily_map[day_str] += e.amount

    categories = [
        {"name": k, "amount": v} for k, v in category_map.items()
    ]

    trends = {
        "labels": list(daily_map.keys()),
        "values": list(daily_map.values())
    }

    # Insights & Budget Status
    insights = []
    if avg_daily > 500:
        insights.append("Your average daily spending is high this period")

    # Calculate monthly category spending for budgets
    monthly_cat_spent = {}
    for e in monthly_expenses:
        monthly_cat_spent[e.category] = monthly_cat_spent.get(e.category, 0) + e.amount
    
    monthly_total = sum(e.amount for e in monthly_expenses)
    
    budget_list = []
    overall_budget = None
    
    for b in budgets:
        used = monthly_cat_spent.get(b.category, 0) if b.category else monthly_total
        cat_name = b.category.title() if b.category else "Overall"
        
        budget_list.append({
            "category": b.category if b.category else "overall",
            "limit": b.amount,
            "used": used,
            "percent": round((used / b.amount) * 100, 1) if b.amount > 0 else 0
        })
        
        if not b.category:
            overall_budget = b

        # Add warnings to insights
        if used > b.amount:
            insights.append(f"⚠️ Budget exceeded for {cat_name}! (₹{used}/₹{b.amount})")
        elif used > b.amount * 0.9:
            insights.append(f"🟠 You've used {round((used/b.amount)*100)}% of your {cat_name} budget")

    # Smart remaining_budget logic
    if overall_budget:
        # If an overall limit is set, that's the source of truth for "Remaining"
        remaining_budget = max(overall_budget.amount - monthly_total, 0)
    else:
        # Fallback: sum of remaining room in categorized budgets
        remaining_budget = sum(max(0, b.amount - monthly_cat_spent.get(b.category, 0)) for b in budgets if b.category)

    return {
        "summary": {
            "totalSpent": total_expense,
            "avgDaily": avg_daily,
            "remainingBudget": round(remaining_budget, 2),
            "changePercent": change_percent
        },
        "categories": categories,
        "trends": trends,
        "insights": insights,
        "budgets": budget_list,
    }
