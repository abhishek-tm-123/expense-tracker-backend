from datetime import datetime, timedelta, date, time

def parse_date_range(text: str):
    today = date.today()

    # Contextual keywords
    if "next month" in text:
        return None, None, "next month"
    if "next week" in text:
        return None, None, "next week"
    if "next" in text:
        return None, None, "next"

    if "previous month" in text:
        return None, None, "previous month"
    if "previous week" in text:
        return None, None, "previous week"
    
    if "previous" in text or "last" in text and "week" not in text and "month" not in text:
         # "previous" or just "last" (without specific timeframe) -> clear context
        return None, None, "previous"

    if "monthly" in text:
        return None, None, "monthly"

    if "today" in text:
        start = datetime.combine(today, time.min)
        end = datetime.combine(today, time.max)
        return start, end, "today"

    if "yesterday" in text:
        y = today - timedelta(days=1)
        start = datetime.combine(y, time.min)
        end = datetime.combine(y, time.max)
        return start, end, "yesterday"

    # Precise "This Week" (Monday to Sunday)
    if "this week" in text or "current week" in text:
        start_day = today - timedelta(days=today.weekday()) # Monday
        start = datetime.combine(start_day, time.min)
        
        # End of week (Sunday)
        end_day = start_day + timedelta(days=6)
        end = datetime.combine(end_day, time.max)
        return start, end, "this week"

    if "last week" in text:
        # Last calendar week (Mon-Sun)
        start_of_this_week = today - timedelta(days=today.weekday())
        start_of_last_week = start_of_this_week - timedelta(days=7)
        end_of_last_week = start_of_last_week + timedelta(days=6)
        
        start = datetime.combine(start_of_last_week, time.min)
        end = datetime.combine(end_of_last_week, time.max)
        return start, end, "last week"

    if "this month" in text:
        start_day = today.replace(day=1)
        start = datetime.combine(start_day, time.min)
        end = datetime.combine(today, time.max)
        return start, end,"this month"

    if "last month" in text:
        first_this_month = today.replace(day=1)
        last_month_end_day = first_this_month - timedelta(days=1)
        last_month_start_day = last_month_end_day.replace(day=1)
        start = datetime.combine(last_month_start_day, time.min)
        end = datetime.combine(last_month_end_day, time.max)
        return start, end,"last month"

    return None, None,"overall"
