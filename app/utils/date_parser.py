from datetime import datetime, timedelta, date, time

def parse_date_range(text: str):
    today = date.today()

    if "today" in text:
        start = datetime.combine(today, time.min)
        end = datetime.combine(today, time.max)
        return start, end,"today"

    if "yesterday" in text:
        y = today - timedelta(days=1)
        start = datetime.combine(y, time.min)
        end = datetime.combine(y, time.max)
        return start, end,"yesterday"

    if "last week" in text:
        start_day = today - timedelta(days=7)
        start = datetime.combine(start_day, time.min)
        end = datetime.combine(today, time.max)
        return start, end,"last week"

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
