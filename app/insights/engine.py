from typing import List, Dict
from datetime import datetime, timedelta
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import Expense, Budget
from .schemas import Insight
from .analyzers import (
    analyze_budget_health,
    analyze_spending_trends,
    detect_anomalies,
    analyze_category_patterns
)

async def generate_insights(session: AsyncSession, user_id: int) -> List[Insight]:
    """
    Orchestrates data fetching and analysis to generate a prioritized list of insights.
    """
    today = datetime.utcnow().date()
    month_start = today.replace(day=1)
    
    # --- 1. Fetch Data Efficiently ---
    
    # Current Month Expenses (Aggregated by Category)
    stmt_month_cats = select(Expense.category, func.sum(Expense.amount)).where(
        Expense.user_id == user_id,
        Expense.created_at >= month_start
    ).group_by(Expense.category)
    
    # Recent Expenses (for Anomaly Detection - last 30 days)
    lookback_start = today - timedelta(days=30)
    stmt_recent = select(Expense).where(
        Expense.user_id == user_id,
        Expense.created_at >= lookback_start
    ).order_by(Expense.created_at.desc())
    
    # Budgets for Current Month
    stmt_budgets = select(Budget).where(
        Budget.user_id == user_id,
        Budget.month == today.month,
        Budget.year == today.year
    )

    # Previous Month Total (for Trend)
    # Simple check: last month date range
    last_month_end = month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    
    stmt_prev_month = select(func.sum(Expense.amount)).where(
        Expense.user_id == user_id,
        Expense.created_at >= last_month_start,
        Expense.created_at <= last_month_end
    )
    
    # Execute Queries
    # In a real async environment, we could use asyncio.gather for parallelism
    # using session.execute directly here for simplicity
    
    result_cats = await session.execute(stmt_month_cats)
    monthly_cat_spent = {r[0]: r[1] for r in result_cats.all()}
    total_month_spent = sum(monthly_cat_spent.values())
    
    result_recent = await session.execute(stmt_recent)
    recent_expenses = [
        {"title": e.title, "amount": e.amount, "date": e.created_at} 
        for e in result_recent.scalars().all()
    ]
    
    result_budgets = await session.execute(stmt_budgets)
    budgets = [
        {"category": b.category, "amount": b.amount} 
        for b in result_budgets.scalars().all()
    ]
    
    result_prev = await session.execute(stmt_prev_month)
    prev_month_total = result_prev.scalar() or 0
    
    # --- 2. Calculate Derived Metrics ---
    
    # Daily Averages
    days_passed_curr = today.day
    msg_avg_curr = total_month_spent / days_passed_curr if days_passed_curr > 0 else 0
    
    days_in_prev_month = last_month_end.day
    msg_avg_prev = prev_month_total / days_in_prev_month if days_in_prev_month > 0 else 0
    
    # --- 3. Run Analyzers ---
    
    all_insights = []
    
    # Budget Health
    # We need to construct the budget list in the format expected by analyze_budget_health
    # which expects dicts with 'category' and 'amount'
    # And we need to mix in the current spending
    # The analyzer expects: budgets (list of dicts), monthly_spending (dict), total_spent (float)
    
    budget_insights = analyze_budget_health(budgets, monthly_cat_spent, total_month_spent)
    all_insights.extend(budget_insights)
    
    # Spending Trends
    trend_insights = analyze_spending_trends(msg_avg_curr, msg_avg_prev)
    all_insights.extend(trend_insights)
    
    # Anomalies
    anomaly_insights = detect_anomalies(recent_expenses)
    all_insights.extend(anomaly_insights)
    
    # Category Patterns
    pattern_insights = analyze_category_patterns(monthly_cat_spent, total_month_spent)
    all_insights.extend(pattern_insights)
    
    # --- 4. Prioritize and Return ---
    
    # Sort by priority (descending)
    all_insights.sort(key=lambda x: x.priority, reverse=True)
    
    # Format for Frontend (Simple strings for now as requested by user prompt ecosystem, 
    # but the prompt asked for "Example insight messages" which our schema supports.
    # The existing dashboard expects a list of strings. We should probably return objects 
    # if we update the frontend, but the prompt implies backend changes. 
    # Let's return the objects to the caller (dashboard.py) and let dashboard.py decide how to format.
    
    return all_insights
