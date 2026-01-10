import joblib
import nltk
from nltk.stem import WordNetLemmatizer
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession as Session

from .auth import get_current_user
from .database import get_session
from .models import Expense, ChatHistory, Budget
from .schemas import chatMessage
from .utils.entity_extractor import extract_entities, get_professional_response
from .utils.expense_parser import process_expense

# Load ML model with error handling
model_path = Path(__file__).parent / "ml" / "intent_model.pkl"
intent_pipeline = None
try:
    intent_pipeline = joblib.load(model_path)
    print("✓ ML intent model loaded successfully")
except FileNotFoundError:
    print("⚠ Warning: ML model not found. Using rule-based intent detection.")
except Exception as e:
    print(f"⚠ Warning: Could not load ML model: {e}. Using rule-based intent detection.")

# Initialize lemmatizer
try:
    lemmatizer = WordNetLemmatizer()
    lemmatizer.lemmatize("test")
except LookupError:
    nltk.download('wordnet', quiet=True)
    nltk.download('omw-1.4', quiet=True)
    lemmatizer = WordNetLemmatizer()

CONFIDENCE_THRESHOLD = 0.5

def preprocess_text(text: str) -> str:
    """Preprocess text with lemmatization for better intent matching."""
    lemmatizer = WordNetLemmatizer()
    words = text.lower().split()
    lemmatized = [lemmatizer.lemmatize(word) for word in words]
    return " ".join(lemmatized)

def predict_intent_rule_based(text: str) -> dict:
    """Rule-based intent detection fallback when ML model is unavailable."""
    text_lower = text.lower()
    
    # Initialize all intents with low probability
    intents = ["add_expense", "show_expenses", "total_expenses", "set_budget", "show_budget", "unknown"]
    probs = {intent: 0.1 for intent in intents}
    
    # Rule-based detection
    if any(word in text_lower for word in ["spent", "paid", "bought", "purchased"]):
        probs["add_expense"] = 0.8
    elif any(word in text_lower for word in ["show", "list", "view"]):
        if "budget" in text_lower:
            probs["show_budget"] = 0.7
        else:
            probs["show_expenses"] = 0.7
    elif any(word in text_lower for word in ["total", "sum", "how much"]):
        probs["total_expenses"] = 0.7
    elif any(word in text_lower for word in ["set", "limit", "budget"]) and "budget" in text_lower:
        probs["set_budget"] = 0.7
    else:
        probs["unknown"] = 0.6
    
    intent = max(probs, key=probs.get)
    return {
        "intent": intent,
        "confidence": probs[intent],
        "probs": probs
    }

def predict_intent(text: str) -> dict:
    """Predict intent using ML model or rule-based fallback."""
    if intent_pipeline is None:
        return predict_intent_rule_based(text)
    
    try:
        processed = preprocess_text(text)
        probs = intent_pipeline.predict_proba([processed])[0]
        intent_idx = probs.argmax()

        intent = intent_pipeline.classes_[intent_idx]
        confidence = probs[intent_idx]
        
        return {
            "intent": intent,
            "confidence": confidence,
            "probs": dict(zip(intent_pipeline.classes_, probs))
        }
    except Exception as e:
        print(f"ML prediction failed: {e}, using rule-based fallback")
        return predict_intent_rule_based(text)

router = APIRouter(prefix="/chat")

async def save_chat_history(user_id:int, message:str, sender:str, session:Session):   
    chat_entry = ChatHistory(user_id=user_id, message=message, sender=sender)
    session.add(chat_entry)
    await session.commit()
    return chat_entry

@router.get("/history")
async def get_chat_history(session: Session = Depends(get_session), current_user: int = Depends(get_current_user)):
    stmt = select(ChatHistory).where(ChatHistory.user_id == current_user).order_by(ChatHistory.timestamp)
    result = await session.execute(stmt)
    chat_history = result.scalars().all()
    return [
        { "sender": c.sender, "text": c.message, "time": c.timestamp}
        for c in chat_history
    ]

@router.delete("/clear")
async def clear_chat(session: Session = Depends(get_session), current_user: int = Depends(get_current_user)):
    stmt = select(ChatHistory).where(ChatHistory.user_id == current_user)
    result = await session.execute(stmt)
    chats = result.scalars().all()
    for chat in chats:
        await session.delete(chat)
    await session.commit()
    return {"message": "Chat history cleared"}

async def handle_add_expense(entities, user_id, session: Session):
    if not entities["amount"] or not entities["category"]:
        return get_professional_response("add_expense", entities, success=False)
    
    expense = Expense(
        title=f"{entities['category'].title()} expense",
        user_id=user_id,
        amount=entities["amount"],
        category=entities["category"]
    )
    session.add(expense)
    
    # --- BUDGET WARNING LOGIC ---
    now = datetime.now()
    month, year = now.month, now.year
    
    # 1. Total spending for this month
    start_of_month = datetime(year, month, 1)
    stmt_spent = select(Expense).where(
        Expense.user_id == user_id,
        Expense.created_at >= start_of_month
    )
    result = await session.execute(stmt_spent)
    all_expenses = result.scalars().all()
    total_spent = sum(e.amount for e in all_expenses)
    
    # 2. Category spending
    cat_spent = sum(e.amount for e in all_expenses if e.category == entities["category"])
    
    # 3. Check Budgets
    warning = None
    stmt_budgets = select(Budget).where(
        Budget.user_id == user_id, 
        Budget.month == month, 
        Budget.year == year
    )
    result_budgets = await session.execute(stmt_budgets)
    budgets = result_budgets.scalars().all()
    
    for b in budgets:
        # Check specific category budget
        if b.category == entities["category"]:
            if cat_spent > b.amount:
                warning = f"Budget for {b.category.title()} exceeded! (₹{cat_spent}/₹{b.amount})"
            elif cat_spent > b.amount * 0.9:
                warning = f"Approaching {b.category.title()} budget limit. (₹{cat_spent}/₹{b.amount})"
        
        # Check overall budget (where category is None)
        if b.category is None:
            if total_spent > b.amount:
                warning = f"Overall monthly budget exceeded! (₹{total_spent}/₹{b.amount})"
            elif total_spent > b.amount * 0.9:
                warning = f"Approaching overall monthly budget limit. (₹{total_spent}/₹{b.amount})"

    await session.commit()
    return get_professional_response("add_expense", entities, success=True, warning=warning)

async def handle_total_expenses(entities, user_id, session: Session):
    stmt = select(Expense).where(Expense.user_id == user_id)
    if entities["start_date"] and entities["end_date"]:
        stmt = stmt.where(Expense.created_at >= entities["start_date"], Expense.created_at <= entities["end_date"])
    
    result = await session.execute(stmt)
    expenses = result.scalars().all()
    total = sum(e.amount for e in expenses)
    return get_professional_response("total_expenses", entities, data={"total": total})

async def handle_show_expenses(entities, user_id, session: Session):
    stmt = select(Expense).where(Expense.user_id == user_id)
    if entities["start_date"] and entities["end_date"]:
        stmt = stmt.where(Expense.created_at >= entities["start_date"], Expense.created_at <= entities["end_date"])
    
    result = await session.execute(stmt)
    expenses = result.scalars().all()
    return get_professional_response("show_expenses", entities, data={"expenses": expenses})

async def handle_set_budget(entities, user_id, session: Session):
    if not entities["amount"]:
        return get_professional_response("set_budget", entities, success=False)
    
    now = datetime.now()
    month, year = now.month, now.year
    
    # Check if budget already exists
    stmt = select(Budget).where(
        Budget.user_id == user_id,
        Budget.category == entities["category"],
        Budget.month == month,
        Budget.year == year
    )
    result = await session.execute(stmt)
    existing_budget = result.scalars().first()
    
    if existing_budget:
        existing_budget.amount = entities["amount"]
    else:
        budget = Budget(
            user_id=user_id,
            category=entities["category"],
            amount=entities["amount"],
            month=month,
            year=year
        )
        session.add(budget)
    
    await session.commit()
    return get_professional_response("set_budget", entities, success=True)

async def handle_show_budget(entities, user_id, session: Session):
    now = datetime.now()
    month, year = now.month, now.year
    
    # Get budgets
    stmt = select(Budget).where(
        Budget.user_id == user_id,
        Budget.month == month,
        Budget.year == year
    )
    result = await session.execute(stmt)
    budgets = result.scalars().all()
    
    if not budgets:
        return get_professional_response("show_budget", entities, data={"budgets": []})
    
    # Get monthly spending
    start_of_month = datetime(year, month, 1)
    stmt_expenses = select(Expense).where(
        Expense.user_id == user_id,
        Expense.created_at >= start_of_month
    )
    result_expenses = await session.execute(stmt_expenses)
    expenses = result_expenses.scalars().all()
    
    # Calculate spending per category
    spent_map = {}
    for e in expenses:
        spent_map[e.category] = spent_map.get(e.category, 0) + e.amount
    
    # Overall spending
    spent_map[None] = sum(e.amount for e in expenses)
    
    return get_professional_response("show_budget", entities, data={"budgets": budgets, "spent_map": spent_map})

@router.post("/message")
async def chat_endpoint(chatmessage: chatMessage, session: Session = Depends(get_session), current_user: int = Depends(get_current_user)):
    text = chatmessage.message.strip()
    await save_chat_history(current_user, chatmessage.message, 'user', session)

    # 1. Extract Entities (used for boosting and processing)
    entities = extract_entities(text)

    # 2. Predict Intent & Apply Global Boosting
    try:
        result = predict_intent(text)
        probs = result["probs"]  # Dictionary of intent -> probability
        
        # Apply Boosts to probabilities
        # Add Expense Boost
        expense_verbs = ["spent", "paid", "bought", "purchased", "went", "ate", "had", "visit"]
        if any(word in text.lower() for word in expense_verbs):
            probs["add_expense"] = probs.get("add_expense", 0) + 0.4
            
        if entities["amount"]:
            if entities["category"]:
                probs["add_expense"] = probs.get("add_expense", 0) + 0.2
                
        # Set Budget Boost (Require budget-related keywords to avoid false positives)
        budget_keywords = ["limit", "budget", "cap", "target", "set"]
        if any(word in text.lower() for word in budget_keywords):
            if entities["amount"]:
                probs["set_budget"] = probs.get("set_budget", 0) + 0.4
            else:
                probs["set_budget"] = probs.get("set_budget", 0) + 0.2
        elif "budget" not in text.lower():
            # Penalize set_budget if the word 'budget' isn't actually there
            probs["set_budget"] = probs.get("set_budget", 0) - 0.2

        # Show Expenses/Budget Boost
        if any(word in text.lower() for word in ["show", "list", "view", "total", "summary"]):
            if "budget" in text.lower():
                probs["show_budget"] = probs.get("show_budget", 0) + 0.2
            else:
                probs["show_expenses"] = probs.get("show_expenses", 0) + 0.2
                probs["total_expenses"] = probs.get("total_expenses", 0) + 0.2

        # Pick the winner
        intent = max(probs, key=probs.get)
        confidence = probs[intent]
        
        if confidence < CONFIDENCE_THRESHOLD:
            intent = "fallback"
            
    except Exception as e:
        print(f"DEBUG: Prediction error: {e}")
        intent = "fallback"

    # 3. Route to Handler
    if intent == "add_expense":
        # Integrate automatic extraction module
        try:
            parsed = process_expense(text)
            entities["amount"] = parsed["amount"]
            entities["category"] = parsed["category"]
        except:
            pass
            
        response_message = await handle_add_expense(entities, current_user, session)
    elif intent == "total_expenses":
        response_message = await handle_total_expenses(entities, current_user, session)
    elif intent == "show_expenses":
        response_message = await handle_show_expenses(entities, current_user, session)
    elif intent == "set_budget":
        response_message = await handle_set_budget(entities, current_user, session)
    elif intent == "show_budget":
        response_message = await handle_show_budget(entities, current_user, session)
    elif intent == "unknown":
        response_message = get_professional_response("unknown", entities)
    else:
        response_message = get_professional_response("fallback", entities)

    await save_chat_history(current_user, response_message, 'bot', session)
    return {"response": response_message}
