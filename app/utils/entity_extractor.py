import re
from datetime import datetime
from .date_parser import parse_date_range

# Common categories in the system
CATEGORIES = ["food", "travel", "rent", "snacks", "shopping", "fuel", "entertainment", "health", "others"]

def extract_entities(text: str) -> dict:
    """
    Extracts amount, category, and date range from the given text.
    """
    text_lower = text.lower().strip()
    
    # 1. Extract Amount
    # Supports "250", "₹250", "rs 250", "250.50"
    amount_match = re.search(r"(?:rs|₹|\$)?\s?(\d+(?:\.\d{1,2})?)", text_lower)
    amount = float(amount_match.group(1)) if amount_match else None
    
    # 2. Extract Category (Fuzzy/Keyword matching)
    category = None
    for cat in CATEGORIES:
        if cat in text_lower:
            category = cat
            break
    
    # 3. Extract Date Range
    start_date, end_date, label = parse_date_range(text_lower)
    
    return {
        "amount": amount,
        "category": category,
        "start_date": start_date,
        "end_date": end_date,
        "date_label": label
    }

def get_professional_response(intent: str, entities: dict, success: bool = True, data: dict = None) -> str:
    """
    Generates a professional, user-friendly response based on intent and result.
    """
    if intent == "add_expense":
        if success:
            return f"✅ **Expense Added!**\n\nI've recorded a charge of **₹{entities['amount']}** under **{entities['category'].title()}**. Your spending has been updated."
        return "❌ **Oops!** I couldn't quite catch that. Could you please provide the amount and category? (e.g., 'Add 200 for food')"
        
    if intent == "total_expenses":
        total = data.get("total", 0)
        label = entities.get("date_label", "overall")
        return f"📊 **Spending Summary ({label.title()})**\n\nYour total expenses for this period amount to **₹{total}**. Let me know if you need a detailed breakdown!"

    if intent == "show_expenses":
        expenses = data.get("expenses", [])
        label = entities.get("date_label", "overall")
        if not expenses:
            return f"📂 **No expenses found** for {label}. You're all clear!"
        
        lines = [f"• **₹{e.amount}** | {e.category.title()} | {e.created_at.date()}" for e in expenses]
        return f"📝 **Expense Records ({label.title()})**\n\n" + "\n".join(lines)

    if intent == "unknown":
        return (
            "👋 **Hi! I'm your Finance Assistant.**\n\n"
            "I can help you manage your money professionally. Try asking:\n"
            "• \"Add 500 for shopping\"\n"
            "• \"What's my total for this month?\"\n"
            "• \"Show my expenses from last week\"\n"
            "• \"Set a budget of 5000 for food\""
        )
        
    return "🙏 I'm sorry, I didn't quite understand that. Could you try rephrasing? I'm still learning!"
