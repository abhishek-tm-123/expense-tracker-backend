from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession as Session
from datetime import datetime, timedelta, time
from typing import List, Dict, Optional
import asyncio
import numpy as np

from .auth import get_current_user
from .database import get_session
from .models import Expense, Budget

router = APIRouter(prefix="/dashboard")

# --- Helper Functions ---

def safe_division(a: float, b: float) -> float:
    """Mathematical safety to avoid ZeroDivisionError."""
    if b == 0:
        return 0.0
    return a / b

def compute_volatility(values: List[float]) -> float:
    """Computes Coefficient of Variation (CV) as a measure of volatility."""
    if not values or len(values) < 2:
        return 0.0
    mean = np.mean(values)
    if mean <= 0:
        return 0.0
    std = np.std(values)
    return std / mean

def calculate_health_score(
    total_spent: float,
    income: float,
    daily_expenses: List[float],
    total_budget: Optional[float],
    income_history: List[float]
) -> Dict:
    """
    Structured Financial Health Index based on professional advisory logic.
    Returns score, status, and breakdown.
    """
    if income <= 0:
        return {
            "health_score": None,
            "health_status": "Insufficient Income Data",
            "breakdown": {}
        }

    # -- Rule 2: Savings Strength (Weight: 30%) --
    # Reasoning: Higher savings rates are the primary driver of long-term wealth.
    savings_rate = safe_division(income - total_spent, income)
    if savings_rate >= 0.30: savings_score = 100
    elif savings_rate >= 0.15: savings_score = 80
    elif savings_rate >= 0.05: savings_score = 60
    elif savings_rate >= 0: savings_score = 40
    else: savings_score = 10

    # -- Rule 3: Expense Sustainability (Weight: 20%) --
    # Reasoning: Living within means is critical for financial stability.
    expense_ratio = safe_division(total_spent, income)
    if expense_ratio <= 0.60: expense_score = 100
    elif expense_ratio <= 0.80: expense_score = 80
    elif expense_ratio <= 1.00: expense_score = 60
    else: expense_score = 20

    # -- Rule 4: Expense Stability (Weight: 15%) --
    # Reasoning: Low volatility in spending indicates better financial control.
    if len(daily_expenses) >= 5:
        volatility_ratio = compute_volatility(daily_expenses)
        if volatility_ratio < 0.30: stability_score = 100
        elif volatility_ratio <= 0.70: stability_score = 70
        elif volatility_ratio <= 1.20: stability_score = 40
        else: stability_score = 20
    else:
        # Insufficient data, return neutral
        stability_score = 60

    # -- Rule 5: Budget Discipline (Weight: 15%) --
    # Reasoning: Adherence to planned spending demonstrates discipline.
    if total_budget is None or total_budget <= 0:
        budget_score = 60 # Neutral for missing budget
    else:
        usage = safe_division(total_spent, total_budget)
        if usage <= 0.90: budget_score = 100
        elif usage <= 1.00: budget_score = 70
        elif usage <= 1.20: budget_score = 40
        else: budget_score = 10

    # -- Rule 6: Income Consistency (Weight: 20%) --
    # Reasoning: Stable income history provides a safer financial base.
    if len(income_history) >= 3:
        income_volatility = compute_volatility(income_history)
        if income_volatility < 0.10: income_score = 100
        elif income_volatility <= 0.25: income_score = 80
        elif income_volatility <= 0.50: income_score = 50
        else: income_score = 20
    else:
        # Insufficient history, do not penalize new users
        income_score = 60

    # -- Final Weighted Score --
    raw_score = (
        0.30 * savings_score +
        0.20 * expense_score +
        0.15 * stability_score +
        0.15 * budget_score +
        0.20 * income_score
    )
    
    health_score = int(max(0, min(100, round(raw_score))))

    if health_score >= 85: status = "Financially Strong"
    elif health_score >= 70: status = "Stable"
    elif health_score >= 55: status = "Vulnerable"
    elif health_score >= 40: status = "At Risk"
    else: status = "Critical"

    return {
        "health_score": health_score,
        "health_status": status,
        "breakdown": {
            "savings": savings_score,
            "expense": expense_score,
            "stability": stability_score,
            "budget": budget_score,
            "income_consistency": income_score
        }
    }

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
    
    # Income (Current Month)
    from .models import Income
    stmt_income = select(Income).where(
        Income.user_id == current_user,
        Income.month == month,
        Income.year == year
    )

    # Income History (Last 6 Months)
    stmt_income_history = select(Income.amount).where(
        Income.user_id == current_user
    ).order_by(Income.year.desc(), Income.month.desc()).limit(6)

    # EXECUTE QUERIES
    
    result_total = await session.execute(stmt_total)
    total_expense = result_total.scalar() or 0
    
    result_cats = await session.execute(stmt_cats)
    categories = [{"name": r[0], "amount": r[1]} for r in result_cats.all()]
    
    result_trends = await session.execute(stmt_trends)
    trends_rows = result_trends.all()
    
    result_prev = await session.execute(stmt_prev)
    prev_total = result_prev.scalar() or 0
    
    result_month_cats = await session.execute(stmt_month_cats)
    monthly_cat_spent = {r[0]: r[1] for r in result_month_cats.all()}
    monthly_total = sum(monthly_cat_spent.values())
    
    result_budgets = await session.execute(stmt_budgets)
    budgets = result_budgets.scalars().all()
    
    result_income = await session.execute(stmt_income)
    income_record = result_income.scalars().first()
    income_val = income_record.amount if income_record else 0

    result_income_history = await session.execute(stmt_income_history)
    income_history = list(result_income_history.scalars().all())

    # --- PROCESS DATA ---
    
    # Change Percent
    if prev_total > 0:
        change_percent = round(((total_expense - prev_total) / prev_total) * 100, 1)
    else:
        change_percent = 100.0 if total_expense > 0 else 0.0

    # Avg Daily
    days_count = max((end_dt - start_dt).days + 1, 1)
    avg_daily = round(total_expense / days_count, 3)

    # Trend Formatting
    trend_map = {}
    curr = start_dt.date()
    while curr <= end_dt.date():
        trend_map[curr.strftime("%Y-%m-%d")] = 0.0
        curr += timedelta(days=1)
        
    for date_val, amount in trends_rows:
        k = str(date_val)
        if k in trend_map:
            trend_map[k] = round(float(amount), 3)
            
    trends_labels = []
    trends_values = []
    for k in sorted(trend_map.keys()):
        d_obj = datetime.strptime(k, "%Y-%m-%d")
        trends_labels.append(d_obj.strftime("%d %b"))
        trends_values.append(trend_map[k])
        
    trends = {"labels": trends_labels, "values": trends_values}
    
    # Insights (External Engine)
    from app.insights.engine import generate_insights
    structured_insights = await generate_insights(session, current_user)
    insights = [i.message for i in structured_insights]
    
    # Budgets
    budget_list = []
    total_budget_sum = 0.0
    has_budgets = False
    
    for b in budgets:
        has_budgets = True
        used = monthly_cat_spent.get(b.category, 0) if b.category else monthly_total
        budget_list.append({
            "category": b.category if b.category else "overall",
            "limit": round(float(b.amount), 3),
            "used": round(float(used), 3),
            "percent": round((used / b.amount) * 100, 3) if b.amount > 0 else 0.0
        })
        total_budget_sum += b.amount

    remaining_budget = total_budget_sum - monthly_total
    budget_exceeded = remaining_budget < 0

    # Calculate Financial Health Index
    daily_values = list(trend_map.values())
    health_ctx = calculate_health_score(
        total_expense, 
        income_val, 
        daily_values, 
        total_budget_sum if has_budgets else None, 
        income_history
    )

    return {
        "summary": {
            "totalSpent": round(float(total_expense), 3),
            "totalBudget": round(float(total_budget_sum), 3),
            "avgDaily": avg_daily,
            "remainingBudget": round(float(remaining_budget), 3),
            "budgetExceeded": budget_exceeded,
            "changePercent": round(float(change_percent), 3),
            "income": round(float(income_val), 3),
            "incomeMissing": income_val <= 0,
            "savings": round(float(income_val - total_expense), 3) if income_val > 0 else 0.0,
            "healthScore": health_ctx["health_score"],
            "healthStatus": health_ctx["health_status"],
            "healthBreakdown": health_ctx["breakdown"],
            "message": "Add your monthly income through chat to unlock Financial Health Score." if income_val <= 0 else None
        },
        "categories": [{"name": c["name"], "amount": round(float(c["amount"]), 3)} for c in categories],
        "trends": trends,
        "insights": insights,
        "budgets": budget_list,
    }
