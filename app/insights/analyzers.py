from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from collections import defaultdict
import statistics

from .schemas import Insight, InsightType

# --- Helper Functions ---

def calculate_z_scores(values: List[float]) -> List[float]:
    if len(values) < 2:
        return [0.0] * len(values)
    
    mean = statistics.mean(values)
    stdev = statistics.stdev(values)
    
    if stdev == 0:
        return [0.0] * len(values)
        
    return [(x - mean) / stdev for x in values]

# --- Analyzers ---

def analyze_budget_health(budgets: List[Dict], monthly_spending: Dict[str, float], total_spent_month: float) -> List[Insight]:
    """
    Checks for budget overruns and usage warnings.
    """
    insights = []
    
    # 1. Overall Budget Analysis (if applicable)
    # This logic depends on how you structure "overall" budget. 
    # Assuming 'budgets' list contains both category-specific and possibly an overall one.
    
    for budget in budgets:
        category = budget.get("category")
        limit = budget.get("amount", 0)
        
        if limit <= 0:
            continue
            
        if category:
            spent = monthly_spending.get(category, 0)
            label = category.title()
        else:
            # Overall budget
            spent = total_spent_month
            label = "Overall"

        usage_percent = (spent / limit) * 100
        
        if usage_percent >= 100:
            insights.append(Insight(
                type=InsightType.CRITICAL,
                message=f"Budget exceeded for {label}.",
                metric=f"₹{spent} / ₹{limit}",
                action=f"Stop spending on {label} immediately to avoid debt.",
                priority=10
            ))
        elif usage_percent >= 90:
            insights.append(Insight(
                type=InsightType.WARNING,
                message=f"You've used 90% of your {label} budget.",
                metric=f"{int(usage_percent)}%",
                action="Review planned expenses for the rest of the month.",
                priority=8
            ))
        elif usage_percent >= 75 and datetime.utcnow().day < 15:
             # High spending early in the month
             insights.append(Insight(
                type=InsightType.WARNING,
                message=f"Rapid spending in {label} (75% used by mid-month).",
                metric=f"{int(usage_percent)}%",
                action="Pace your spending to last the month.",
                priority=7
            ))

    return insights

def analyze_spending_trends(current_month_daily_avg: float, prev_month_daily_avg: float) -> List[Insight]:
    """
    Compares daily average spending between months.
    """
    insights = []
    
    if prev_month_daily_avg <= 0:
        return insights # Cannot compare
        
    change_percent = ((current_month_daily_avg - prev_month_daily_avg) / prev_month_daily_avg) * 100
    
    if change_percent > 20:
        insights.append(Insight(
            type=InsightType.WARNING,
            message="Spending is significantly higher than last month.",
            metric=f"+{change_percent:.1f}%",
            action="Check for unusual one-time expenses.",
            priority=6
        ))
    elif change_percent < -10:
        insights.append(Insight(
            type=InsightType.POSITIVE,
            message="You are spending less than last month!",
            metric=f"{change_percent:.1f}%",
            action="Great job! Consider saving the surplus.",
            priority=5
        ))
        
    return insights

def detect_anomalies(recent_expenses: List[Dict]) -> List[Insight]:
    """
    Uses Z-score to find unusually high single expenses in the recent list.
    Expects recent_expenses to be a list of dicts with 'amount', 'title', 'date'.
    """
    insights = []
    
    if len(recent_expenses) < 5:
        return insights
        
    amounts = [e['amount'] for e in recent_expenses]
    z_scores = calculate_z_scores(amounts)
    
    # Check the most recent few expenses for anomalies
    # unique_anomalies = set()

    for i, z in enumerate(z_scores):
        # corresponding expense
        exp = recent_expenses[i]
        
        # We only care about high anomalies (z > 2.0 means top ~2.5% of curve)
        if z > 2.5:
             insights.append(Insight(
                type=InsightType.WARNING,
                message=f"Unusual high expense detected: {exp['title']}",
                metric=f"₹{exp['amount']}",
                action="Verify this wasn't an accidental duplicate.",
                priority=7
            ))
    
    # Deduplicate by message if needed, but here we just return top ones
    return insights[:2] # Limit number of anomalies reported

def analyze_category_patterns(monthly_spending: Dict[str, float], total_spent: float) -> List[Insight]:
    """
    Identifies top spending categories.
    """
    insights = []
    if total_spent <= 0:
        return insights
        
    sorted_cats = sorted(monthly_spending.items(), key=lambda x: x[1], reverse=True)
    
    if not sorted_cats:
        return insights
        
    top_cat, top_amt = sorted_cats[0]
    percent = (top_amt / total_spent) * 100
    
    if percent > 40:
         insights.append(Insight(
            type=InsightType.INFO,
            message=f"Most of your money goes to {top_cat.title()}.",
            metric=f"{int(percent)}%",
            action=f"See if you can reduce {top_cat} expenses.",
            priority=4
        ))
        
    return insights
