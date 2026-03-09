from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from sqlmodel import select, func, and_
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import Expense, Budget, Income
from .schemas import Insight
from .analyzers import (
    analyze_budget_health,
    analyze_spending_trends,
    detect_anomalies,
    analyze_category_patterns,
    analyze_pacing,
    analyze_streaks,
    analyze_velocity,
    analyze_dormancy
)

async def generate_insights(session: AsyncSession, user_id: int) -> List[Insight]:
    """
    Orchestrates data fetching and analysis to generate a prioritized list of insights.
    """
    today = datetime.utcnow().date()
    month_start = today.replace(day=1)
    
    # --- 1. Fetch Current Month Data ---
    
    # Aggregated spending by category
    stmt_month_cats = select(Expense.category, func.sum(Expense.amount)).where(
        Expense.user_id == user_id,
        Expense.created_at >= month_start
    ).group_by(Expense.category)
    
    # Budgets for current month
    stmt_budgets = select(Budget).where(
        Budget.user_id == user_id,
        Budget.month == today.month,
        Budget.year == today.year
    )

    # Current month income
    stmt_income = select(func.sum(Income.amount)).where(
        Income.user_id == user_id,
        Income.month == today.month,
        Income.year == today.year
    )

    # --- 2. Fetch Historical Data (Last 6 Months) ---
    
    # Calculate start date for 6 months lookback
    six_months_ago = (month_start - timedelta(days=1)).replace(day=1) - timedelta(days=150)
    six_months_start = six_months_ago.replace(day=1)

    # Monthly totals for streaks and trends
    stmt_history = select(
        func.extract('month', Expense.created_at).label('m'),
        func.extract('year', Expense.created_at).label('y'),
        func.sum(Expense.amount)
    ).where(
        Expense.user_id == user_id,
        Expense.created_at >= six_months_start,
        Expense.created_at < month_start
    ).group_by('y', 'm')

    # Historical budgets to compare against history
    stmt_hist_budgets = select(
        Budget.month, Budget.year, func.sum(Budget.amount)
    ).where(
        Budget.user_id == user_id,
        Budget.year >= six_months_start.year
    ).group_by(Budget.year, Budget.month)

    # --- 3. Fetch Daily Data & Dormancy ---
    
    # Daily spending for velocity (last 14 days)
    stmt_daily = select(
        func.date(Expense.created_at).label('d'),
        func.sum(Expense.amount)
    ).where(
        Expense.user_id == user_id,
        Expense.created_at >= today - timedelta(days=14)
    ).group_by('d')

    # Last spend date per category for dormancy
    stmt_dormancy = select(
        Expense.category, func.max(Expense.created_at)
    ).where(Expense.user_id == user_id).group_by(Expense.category)

    # --- 4. Execute & Process Queries ---
    
    res_cats = await session.execute(stmt_month_cats)
    monthly_cat_spent = {r[0]: float(r[1]) for r in res_cats.all()}
    total_month_spent = sum(monthly_cat_spent.values())
    
    res_budgets = await session.execute(stmt_budgets)
    current_budgets = [{"category": b.category, "amount": b.amount} for b in res_budgets.scalars().all()]
    total_budget_limit = sum(b['amount'] for b in current_budgets)

    res_income = await session.execute(stmt_income)
    current_income = float(res_income.scalar() or 0)

    res_history = await session.execute(stmt_history)
    hist_spending = {(int(r[1]), int(r[0])): float(r[2]) for r in res_history.all()}

    res_hist_budgets = await session.execute(stmt_hist_budgets)
    hist_budgets = {(int(r[1]), int(r[0])): float(r[2]) for r in res_hist_budgets.all()}

    res_daily = await session.execute(stmt_daily)
    daily_spend = {r[0]: float(r[1]) for r in res_daily.all()}

    res_dormancy = await session.execute(stmt_dormancy)
    category_last_spend = {r[0]: r[1] for r in res_dormancy.all()}

    # --- 5. Run Analyzers ---
    
    all_insights = []
    
    # Legacy/Critical Analyzers
    all_insights.extend(analyze_budget_health(current_budgets, monthly_cat_spent, total_month_spent))
    
    # Trends
    prev_month_date = (month_start - timedelta(days=1))
    prev_month_spent = hist_spending.get((prev_month_date.year, prev_month_date.month), 0)
    all_insights.extend(analyze_spending_trends(
        total_month_spent / today.day if today.day > 0 else 0, 
        prev_month_spent / prev_month_date.day
    ))

    # New Smart/Companion Analyzers
    all_insights.extend(analyze_pacing(total_month_spent, total_budget_limit, today.day))
    all_insights.extend(analyze_streaks(hist_spending, hist_budgets))
    all_insights.extend(analyze_velocity(daily_spend))
    all_insights.extend(analyze_dormancy(category_last_spend))
    all_insights.extend(analyze_category_patterns(monthly_cat_spent, total_month_spent))
    
    # --- 6. Prioritize & Return ---
    
    # Sort by priority (descending)
    all_insights.sort(key=lambda x: x.priority, reverse=True)
    
    # Return top 6 most impactful insights
    return all_insights[:6]
