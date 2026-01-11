from .date_parser import parse_date_range
from .expense_parser import extract_amount, detect_category

# Common categories in the system
CATEGORIES = ["food", "travel", "rent", "snacks", "shopping", "fuel", "entertainment", "health", "others"]

def extract_entities(text: str) -> dict:
    """
    Extracts amount, category, and date range from the given text.
    Uses the robust expense_parser for better accuracy.
    """
    text_lower = text.lower().strip()
    
    # 1. Extract Amount
    try:
        amount = extract_amount(text_lower)
    except ValueError:
        amount = None
    
    # 2. Extract Category
    # If a specific category exists in text, we prefer the parser's logic
    category = detect_category(text_lower)
    if category == "others":
        # Check if the user mentioned a category name directly
        for cat in CATEGORIES:
            if cat in text_lower:
                category = cat
                break
    
    # 3. Extract Date Range
    start_date, end_date, label = parse_date_range(text_lower)
    
    return {
        "amount": amount,
        "category": category if category != "others" else None,
        "start_date": start_date,
        "end_date": end_date,
        "date_label": label
    }

def get_professional_response(intent: str, entities: dict, success: bool = True, data: dict = None, warning: str = None) -> str:
    """
    Generates a professional, user-friendly response based on intent and result.
    """
    if intent == "add_expense":
        if success:
            msg = f"✅ **Expense Added!**\n\nI've recorded a charge of **₹{entities['amount']}** under **{entities['category'].title()}**. Your spending has been updated."
            if warning:
                msg += f"\n\n⚠️ **Warning**: {warning}"
            return msg
        return "❌ **Oops!** I couldn't quite catch that. Could you please provide the amount and category? (e.g., 'Add 200 for food')"
        
    if intent == "total_expenses":
        total = data.get("total", 0)
        label = entities.get("date_label", "overall")
        category = entities.get("category")
        
        if category:
            return f"📊 **{category.title()} Spending Summary ({label.title()})**\n\nYour total {category} expenses for this period amount to **₹{total}**. Let me know if you need a detailed breakdown!"
        return f"📊 **Spending Summary ({label.title()})**\n\nYour total expenses for this period amount to **₹{total}**. Let me know if you need a detailed breakdown!"

    if intent == "show_expenses":
        expenses = data.get("expenses", [])
        label = entities.get("date_label", "overall")
        category = entities.get("category")
        
        if not expenses:
            cat_msg = f" in {category.title()}" if category else ""
            return f"📂 **No expenses found**{cat_msg} for {label}. You're all clear!"
        
        lines = [f"• **₹{e.amount}** | {e.category.title()} | {e.created_at.date()}" for e in expenses]
        header = f"📝 **{category.title()} Expense Records ({label.title()})**" if category else f"📝 **Expense Records ({label.title()})**"
        return header + "\n\n" + "\n".join(lines)

    if intent == "unknown":
        return (
            "👋 **Hi! I'm your Finance Assistant.**\n\n"
            "I can help you manage your money professionally. Try asking:\n"
            "• \"Add 500 for shopping\"\n"
            "• \"What's my total for this month?\"\n"
            "• \"Show my expenses from last week\"\n"
            "• \"Set a budget of 5000 for food\"\n"
            "• \"Show my budget details\""
        )
        
    if intent == "set_budget":
        if success:
            cat_str = f" for **{entities['category'].title()}**" if entities['category'] else ""
            return f"🎯 **Budget Set!**\n\nI've set your monthly spending limit to **₹{entities['amount']}**{cat_str}. I'll help you stay on track!"
        return "❌ **Budget not set.** Please specify an amount. (e.g., 'Set a budget of 5000')"

    if intent == "show_budget":
        budgets = data.get("budgets", [])
        if not budgets:
            return "📋 **No budgets set yet.** You can set one by saying something like 'Set a budget of 5000 for food'."
        
        lines = []
        for b in budgets:
            cat = b.category.title() if b.category else "Overall"
            spent = data.get("spent_map", {}).get(b.category, 0)
            percent = (spent / b.amount) * 100 if b.amount > 0 else 0
            lines.append(f"• **{cat}**: ₹{spent} / ₹{b.amount} ({percent:.1f}%)")
        
        return "📉 **Your Monthly Budgets**\n\n" + "\n".join(lines)

    return "🙏 I'm sorry, I didn't quite understand that. Could you try rephrasing? I'm still learning!"
