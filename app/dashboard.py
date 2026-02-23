from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession as Session
from datetime import datetime, timedelta, time
import asyncio
import numpy as np

from .auth import get_current_user
from .database import get_session
from .models import Expense, Budget

router = APIRouter(prefix="/dashboard")

def calculate_health_score(total_spent, income, daily_values):
    if income <= 0:
        return 50, "Moderate"

    savings = income - total_spent
    savings_rate = savings / income
    expense_ratio = total_spent / income
    
    avg_daily = total_spent / len(daily_values) if daily_values else 0
    std_dev = np.std(daily_values) if daily_values else 0
    volatility_ratio = std_dev / avg_daily if avg_daily > 0 else 0

    # 1. Savings Score (50%)
    if savings_rate >= 0.3: savings_score = 100
    elif savings_rate >= 0.15: savings_score = 80
    elif savings_rate >= 0.05: savings_score = 60
    elif savings_rate >= 0: savings_score = 40
    else: savings_score = 20

    # 2. Expense Score (25%)
    if expense_ratio <= 0.6: expense_score = 100
    elif expense_ratio <= 0.8: expense_score = 80
    elif expense_ratio <= 1.0: expense_score = 60
    else: expense_score = 20

    # 3. Stability Score (25%)
    if volatility_ratio < 0.5: stability_score = 100
    elif volatility_ratio <= 1.0: stability_score = 70
    else: stability_score = 40

    health_score = int(0.5 * savings_score + 0.25 * expense_score + 0.25 * stability_score)
    health_score = max(0, min(100, health_score))

    if health_score >= 80: status = "Excellent"
    elif health_score >= 60: status = "Good"
    elif health_score >= 40: status = "Moderate"
    elif health_score >= 20: status = "Risky"
    else: status = "Critical"

    return health_score, status

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
    
    # --- 1. Main Range Aggregations ---
    # Total Spent
    stmt_total = select(func.sum(Expense.amount)).where(
        Expense.user_id == current_user,
        Expense.created_at >= start_dt,
        Expense.created_at <= end_dt
    )
    
    # Category Breakdown
    stmt_cats = select(Expense.category, func.sum(Expense.amount)).where(
        Expense.user_id == current_user,
        Expense.created_at >= start_dt,
        Expense.created_at <= end_dt
    ).group_by(Expense.category)

    # Trends (Group by Date)
    # Using simple date casting (SQLite compatible)
    stmt_trends = select(func.date(Expense.created_at), func.sum(Expense.amount)).where(
        Expense.user_id == current_user,
        Expense.created_at >= start_dt,
        Expense.created_at <= end_dt
    ).group_by(func.date(Expense.created_at))

    # --- 2. Previous Period (for Change %) ---
    period_days = (end_dt - start_dt).days + 1
    prev_start = start_dt - timedelta(days=period_days)
    prev_end = start_dt - timedelta(seconds=1)
    
    stmt_prev = select(func.sum(Expense.amount)).where(
        Expense.user_id == current_user,
        Expense.created_at >= prev_start,
        Expense.created_at <= prev_end
    )
    
    # --- 3. Monthly (for Budget) ---
    now = datetime.utcnow()
    month, year = now.month, now.year
    month_start = datetime(year, month, 1)

    # Monthly Category Spend
    stmt_month_cats = select(Expense.category, func.sum(Expense.amount)).where(
        Expense.user_id == current_user,
        Expense.created_at >= month_start
    ).group_by(Expense.category)
    
    # Budgets
    stmt_budgets = select(Budget).where(
        Budget.user_id == current_user,
        Budget.month == month,
        Budget.year == year
    )
    
    # Income (New)
    from .models import Income
    stmt_income = select(Income).where(
        Income.user_id == current_user,
        Income.month == month,
        Income.year == year
    )

    # EXECUTE QUERIES SEQUENTIALLY (Session assumes single connection)
    
    # 1. Total
    result_total = await session.execute(stmt_total)
    total_expense = result_total.scalar() or 0
    
    # 2. Categories
    result_cats = await session.execute(stmt_cats)
    categories_rows = result_cats.all()
    categories = [{"name": r[0], "amount": r[1]} for r in categories_rows]
    
    # 3. Trends
    result_trends = await session.execute(stmt_trends)
    trends_rows = result_trends.all()
    
    # 4. Prev Total
    result_prev = await session.execute(stmt_prev)
    prev_total = result_prev.scalar() or 0
    
    # 5. Month Cats
    result_month_cats = await session.execute(stmt_month_cats)
    month_cats_rows = result_month_cats.all()
    monthly_cat_spent = {r[0]: r[1] for r in month_cats_rows}
    monthly_total = sum(monthly_cat_spent.values())
    
    # 6. Budgets
    result_budgets = await session.execute(stmt_budgets)
    budgets = result_budgets.scalars().all()
    
    # 7. Income
    result_income = await session.execute(stmt_income)
    income_record = result_income.scalars().first()
    income_val = income_record.amount if income_record else 0

    # --- PROCESS DATA ---
    
    # Change Percent
    if prev_total > 0:
        change_percent = round(((total_expense - prev_total) / prev_total) * 100, 1)
    else:
        change_percent = 100.0 if total_expense > 0 else 0.0

    # Avg Daily
    days_count = max((end_dt - start_dt).days + 1, 1) # +1 inclusive
    avg_daily = round(total_expense / days_count, 2) if days_count > 0 else 0

    # Trend Formatting (Fill Gaps)
    trend_map = {}
    curr = start_dt.date()
    # Fill range with 0
    while curr <= end_dt.date():
        trend_map[curr.strftime("%Y-%m-%d")] = 0
        curr += timedelta(days=1)
        
    # Populate actuals
    for date_val, amount in trends_rows:
        # date_val is usually a string 'YYYY-MM-DD' in SQLite, or date obj in PG
        k = str(date_val)
        if k in trend_map:
            trend_map[k] = amount
            
    # Convert to frontend format ("DD %b")
    sorted_keys = sorted(trend_map.keys())
    trends_labels = []
    trends_values = []
    
    for k in sorted_keys:
        d_obj = datetime.strptime(k, "%Y-%m-%d")
        trends_labels.append(d_obj.strftime("%d %b"))
        trends_values.append(trend_map[k])
        
    trends = {
        "labels": trends_labels,
        "values": trends_values
    }
    
    # Insights & Budgets
    
    # --- NEW: Advanced Insights Engine ---
    from app.insights.engine import generate_insights
    structured_insights = await generate_insights(session, current_user)
    
    # Convert to simple strings for backward compatibility
    insights = [i.message for i in structured_insights]
    
    # Fallback legacy check (optional, can be removed if coverage is good)
    # Keeping budget logic for the 'budgets' list response
    
    budget_list = []
    overall_budget = None
    
    for b in budgets:
        used = monthly_cat_spent.get(b.category, 0) if b.category else monthly_total
        
        budget_list.append({
            "category": b.category if b.category else "overall",
            "limit": b.amount,
            "used": used,
            "percent": round((used / b.amount) * 100, 1) if b.amount > 0 else 0
        })
        
        if not b.category:
            overall_budget = b

    # Remaining Budget Logic
    if overall_budget:
        remaining_budget = overall_budget.amount - monthly_total
    else:
        # Sum of remaining in categorized budgets
        remaining_budget = sum(b.amount - monthly_cat_spent.get(b.category, 0) for b in budgets if b.category)

    budget_exceeded = remaining_budget < 0

    # Calculate Financial Health Score
    total_budget = sum(b.amount for b in budgets)
    income_missing = income_val <= 0
    if not income_missing:
        daily_values = list(trend_map.values())
        health_score, health_status = calculate_health_score(total_expense, income_val, daily_values)
    else:
        health_score = 0
        health_status = "Pending Income"

    return {
        "summary": {
            "totalSpent": total_expense,
            "totalBudget": total_budget,
            "avgDaily": avg_daily,
            "remainingBudget": round(remaining_budget, 2),
            "budgetExceeded": budget_exceeded,
            "changePercent": change_percent,
            "income": income_val,
            "incomeMissing": income_missing,
            "savings": round(income_val - total_expense, 2) if not income_missing else 0,
            "healthScore": health_score,
            "healthStatus": health_status,
            "message": "Add your monthly income through chat to unlock Financial Health Score." if income_missing else None
        },
        "categories": categories,
        "trends": trends,
        "insights": insights,
        "budgets": budget_list,
    }
