from fastapi import APIRouter,Depends,HTTPException
from sqlmodel import Session,select
from datetime import datetime, timedelta
from .auth import get_current_user
from .database import get_session
from .models import Expense

router = APIRouter(prefix="/dashboard")

from datetime import datetime, timedelta, time

def get_date_range(range: str):
    today = datetime.utcnow().date()

    if range == "week":
        start_date = today - timedelta(days=7)
    elif range == "month":
        start_date = today - timedelta(days=30)
    else:
        raise HTTPException(400, "Invalid range. Use 'week', 'month'")

    start_dt = datetime.combine(start_date, time.min)   # 00:00:00
    end_dt   = datetime.combine(today, time.max)        # 23:59:59.999999

    return start_dt, end_dt


@router.get("")
def get_dashboard(
    range: str,
    session: Session = Depends(get_session),
    current_user: int = Depends(get_current_user)
):
    start_date, end_date = get_date_range(range)

    expenses = session.exec(
        select(Expense).where(
            Expense.user_id == current_user,
            Expense.created_at >= start_date,
            Expense.created_at <= end_date
        )
    ).all()

    return build_dashboard_response(expenses, start_date, end_date)

def build_dashboard_response(expenses, start_date, end_date):
    total_expense = sum(exp.amount for exp in expenses)
    days = max((end_date - start_date).days, 1)
    avg_daily = round(total_expense / days, 2)
    
    category_map = {}
    daily_map = {}

    for e in expenses:  
        category_map[e.category] = category_map.get(e.category, 0) + e.amount

        day = e.created_at.strftime("%d %b")
        daily_map[day] = daily_map.get(day, 0) + e.amount

    categories = [
        {"name": k, "amount": v} for k, v in category_map.items()
    ]

    trends = {
        "labels": list(daily_map.keys()),
        "values": list(daily_map.values())
    }

    insights = []
    if avg_daily > 500:
        insights.append("Your average daily spending is high this period")

    return {
        "summary": {
            "totalSpent": total_expense,
            "avgDaily": avg_daily,
            "remainingBudget": 0,
            "changePercent": 0
        },
        "categories": categories,
        "trends": trends,
        "insights": insights,
        "budget": [],
    }