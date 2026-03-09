from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import statistics
import calendar

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

def get_month_info(date_obj: datetime) -> Tuple[int, int]:
    """Returns (current_day, total_days_in_month)"""
    last_day = calendar.monthrange(date_obj.year, date_obj.month)[1]
    return date_obj.day, last_day

# --- Analyzers ---

def analyze_budget_health(budgets: List[Dict], monthly_spending: Dict[str, float], total_spent_month: float) -> List[Insight]:
    """Checks for budget overruns and highlights safe spending."""
    insights = []
    
    for budget in budgets:
        category = budget.get("category")
        limit = budget.get("amount", 0)
        if limit <= 0: continue
            
        spent = monthly_spending.get(category, total_spent_month if not category else 0)
        label = category.title() if category else "Overall"
        usage_percent = (spent / limit) * 100
        
        if usage_percent >= 100:
            insights.append(Insight(
                type=InsightType.CRITICAL,
                message=f"Budget exceeded for {label}.",
                metric=f"₹{int(spent)} / ₹{int(limit)}",
                action=f"Reduce {label} spending to stay on track.",
                priority=10
            ))
        elif usage_percent > 90:
            insights.append(Insight(
                type=InsightType.WARNING,
                message=f"You've used {int(usage_percent)}% of your {label} budget.",
                metric=f"₹{int(limit - spent)} left",
                action="Be careful with non-essential purchases.",
                priority=8
            ))
    return insights

def analyze_pacing(total_spent: float, total_budget: float, current_day: int) -> List[Insight]:
    """Analyzes if spending is 'paced' well for the month."""
    insights = []
    if total_budget <= 0: return insights
    
    _, days_in_month = get_month_info(datetime.utcnow())
    month_progress = current_day / days_in_month
    budget_usage = total_spent / total_budget
    
    # 1. Great pacing (Positive)
    if 0.4 <= month_progress <= 0.6 and budget_usage < (month_progress * 0.8):
        insights.append(Insight(
            type=InsightType.POSITIVE,
            message="Your pacing is incredible! Halfway through and well under budget.",
            metric=f"{int(budget_usage*100)}% used",
            action="At this rate, you'll have a healthy surplus for savings.",
            priority=8,
            metadata={"progress": budget_usage}
        ))
    
    # 2. Predicted Overrun (Proactive Warning)
    if current_day > 7 and budget_usage > (month_progress * 1.2) and budget_usage < 1.0:
        over_amt = int(total_spent - (total_budget * month_progress))
        insights.append(Insight(
            type=InsightType.WARNING,
            message="Early warning: You're spending faster than usual.",
            metric=f"₹{over_amt} over pace",
            action="Try a 'No Spend' weekend to get back in line.",
            priority=7
        ))
    return insights

def analyze_streaks(hist_spending: Dict[Tuple[int, int], float], hist_budgets: Dict[Tuple[int, int], float]) -> List[Insight]:
    """Identifies streaks and milestones (Celebratory)."""
    insights = []
    now = datetime.utcnow()
    streak = 0
    
    # Check last 6 months in reverse
    for i in range(1, 7):
        prev_date = (now.replace(day=1) - timedelta(days=i*28)).replace(day=1)
        key = (prev_date.year, prev_date.month)
        
        spent = hist_spending.get(key)
        limit = hist_budgets.get(key)
        
        if spent is not None and limit is not None and spent <= limit:
            streak += 1
        elif spent is not None: # Broke streak
            break

    if streak >= 3:
        insights.append(Insight(
            type=InsightType.STREAK,
            message=f"Unstoppable! {streak} months in a row under budget.",
            metric=f"{streak} Month Streak",
            action="You're building elite financial habits.",
            priority=9,
            metadata={"streak_count": streak}
        ))
    elif streak == 1:
         insights.append(Insight(
            type=InsightType.POSITIVE,
            message="Nice win! You stayed under budget last month.",
            metric="Goal Hit",
            action="Keep this momentum going for March!",
            priority=5
        ))
    return insights

def analyze_velocity(daily_spend: Dict[datetime, float]) -> List[Insight]:
    """Detects multi-day spending bursts (Velocity)."""
    insights = []
    if len(daily_spend) < 5: return insights
    
    sorted_days = sorted(daily_spend.keys())
    values = [daily_spend[d] for d in sorted_days]
    
    # Rolling 3-day window
    for i in range(len(values) - 2):
        window_sum = sum(values[i:i+3])
        # Only flag if significant (e.g. > 15% of average month or absolute ₹5000)
        if window_sum > 5000:
            insights.append(Insight(
                type=InsightType.WARNING,
                message="Spending Heatwave: High activity over the last 3 days.",
                metric=f"₹{int(window_sum)} burst",
                action="Daily 'small' spends are adding up fast.",
                priority=7,
                metadata={"days": 3}
            ))
            break # Only report the most recent burst
            
    return insights

def analyze_dormancy(category_last_spend: Dict[str, datetime]) -> List[Insight]:
    """Detects categories you haven't spent in (Nudge)."""
    insights = []
    now = datetime.utcnow()
    
    for cat, last_date in category_last_spend.items():
        days_ago = (now - last_date).days
        if 45 <= days_ago <= 90:
            insights.append(Insight(
                type=InsightType.INFO,
                message=f"Category 'cleanse'? No {cat} spend for {days_ago} days.",
                metric="Dormant",
                action=f"If this was a subscription, you might be safe to cancel it!",
                priority=6
            ))
    return insights

def analyze_spending_trends(current_avg: float, prev_avg: float) -> List[Insight]:
    """Compares daily averages with a positive twist."""
    insights = []
    if prev_avg <= 0: return insights
    
    diff = prev_avg - current_avg
    if diff > 100: # Saving ₹100+ per day
        insights.append(Insight(
            type=InsightType.POSITIVE,
            message=f"Daily spending is down ₹{int(diff)} vs last month!",
            metric="Trend Down",
            action="You're effectively saving an extra ₹3000/mo.",
            priority=8
        ))
    elif diff < -500: # Spending much more
        insights.append(Insight(
            type=InsightType.WARNING,
            message="Spending is picking up speed compared to last month.",
            metric="Trend Up",
            action="Check if these are essential or impulsives.",
            priority=6
        ))
    return insights

def analyze_category_patterns(monthly_spending: Dict[str, float], total_spent: float) -> List[Insight]:
    """Standard category analysis."""
    insights = []
    if total_spent <= 0: return insights
    
    top_cat = max(monthly_spending, key=monthly_spending.get)
    top_amt = monthly_spending[top_cat]
    percent = (top_amt / total_spent) * 100
    
    if percent > 40:
        insights.append(Insight(
            type=InsightType.INFO,
            message=f"Insight: {top_cat.title()} is your main expense focus.",
            metric=f"{int(percent)}% of total",
            action=f"Any recurring {top_cat} costs to optimize?",
            priority=4
        ))
    return insights

def detect_anomalies(recent_expenses: List[Dict]) -> List[Insight]:
    """Stub to maintain compatibility in engine.py while we transition to velocity."""
    return []
