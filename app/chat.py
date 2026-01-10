import joblib
import re
import nltk
from nltk.stem import WordNetLemmatizer
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession as Session

from .auth import get_current_user
from .database import get_session
from .schemas import chatMessage
from .models import Expense, ChatHistory, Budget
from .utils.entity_extractor import extract_entities, get_professional_response
from .utils.expense_parser import process_expense

# Ensure NLTK data is available
try:
    nltk.download('wordnet', quiet=True)
    nltk.download('omw-1.4', quiet=True)
except Exception:
    pass

lemmatizer = WordNetLemmatizer()

def preprocess_text(text):
    # Lowercase, remove special chars, and lemmatize
    text = text.lower()
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    tokens = text.split()
    lemmatized = [lemmatizer.lemmatize(w) for w in tokens]
    return " ".join(lemmatized)

BASE_DIR = Path(__file__).resolve().parent
ML_DIR = BASE_DIR / "ml"

# Load the trained model and vectorizer
intent_pipeline = joblib.load(ML_DIR / "intent_pipeline_v1.pkl")

CONFIDENCE_THRESHOLD = 0.5  # start conservative

def predict_intent(text: str) -> dict:
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
<<<<<<< HEAD
    await session.commit()
    return get_professional_response("add_expense", entities, success=True)
=======
    
    # --- BUDGET WARNING LOGIC ---
    now = datetime.now()
    month, year = now.month, now.year
    
    # 1. Total spending for this month
    start_of_month = datetime(year, month, 1)
    stmt_spent = select(Expense).where(
        Expense.user_id == user_id,
        Expense.created_at >= start_of_month
    )
    all_expenses = session.exec(stmt_spent).all()
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
    budgets = session.exec(stmt_budgets).all()
    
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

    session.commit()
    return get_professional_response("add_expense", entities, success=True, warning=warning)
>>>>>>> working-branch

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

def handle_set_budget(entities, user_id, session):
    if not entities["amount"]:
        return get_professional_response("set_budget", entities, success=False)
    
    now = datetime.now()
    month = now.month
    year = now.year
    
    # In a more advanced version, we could extract month/year from entities
    # For now, we default to the current month/year.
    
    statement = select(Budget).where(
        Budget.user_id == user_id,
        Budget.category == entities["category"],
        Budget.month == month,
        Budget.year == year,
    )
    budget = session.exec(statement).first()

    if budget:
        budget.amount = entities["amount"]
    else:
        budget = Budget(
            user_id=user_id,
            category=entities["category"],
            amount=entities["amount"],
            month=month,
            year=year,
        )
        session.add(budget)
    
    session.commit()
    return get_professional_response("set_budget", entities, success=True)

def handle_show_budget(entities, user_id, session):
    now = datetime.now()
    month, year = now.month, now.year
    
    stmt = select(Budget).where(Budget.user_id == user_id, Budget.month == month, Budget.year == year)
    if entities["category"]:
        stmt = stmt.where(Budget.category == entities["category"])
    
    budgets = session.exec(stmt).all()
    
    # Calculate spending for those budgets
    start_of_month = datetime(year, month, 1)
    stmt_spent = select(Expense).where(Expense.user_id == user_id, Expense.created_at >= start_of_month)
    expenses = session.exec(stmt_spent).all()
    
    spent_map = {}
    # Categorized spending
    for cat in set(e.category for e in expenses):
        spent_map[cat] = sum(e.amount for e in expenses if e.category == cat)
    # Overall spending (None key)
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
        
<<<<<<< HEAD
        # --- HYBRID BOOSTING LOGIC ---
        if intent == "add_expense" and entities["amount"] and entities["category"]:
            confidence += 0.3
        elif intent in ["total_expenses", "show_expenses"] and entities["date_label"] != "overall":
            confidence += 0.2
=======
        # Apply Boosts to probabilities
        # Add Expense Boost
        expense_verbs = ["spent", "paid", "bought", "purchased", "went", "ate", "had", "visit"]
        if any(word in text.lower() for word in expense_verbs):
            probs["add_expense"] = probs.get("add_expense", 0) + 0.4
>>>>>>> working-branch
            
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
            
        print(f"DEBUG: Winner={intent}, Score={confidence:.2f}")
    except Exception as e:
        print(f"DEBUG: Prediction error: {e}")
        intent = "fallback"

    # 3. Route to Handler
    if intent == "add_expense":
<<<<<<< HEAD
        response_message = await handle_add_expense(entities, current_user, session)
=======
        # Integrate automatic extraction module
        try:
            parsed = process_expense(text)
            entities["amount"] = parsed["amount"]
            entities["category"] = parsed["category"]
        except Exception:
            pass
            
        response_message = handle_add_expense(entities, current_user, session)
>>>>>>> working-branch
    elif intent == "total_expenses":
        response_message = await handle_total_expenses(entities, current_user, session)
    elif intent == "show_expenses":
<<<<<<< HEAD
        response_message = await handle_show_expenses(entities, current_user, session)
=======
        response_message = handle_show_expenses(entities, current_user, session)
    elif intent == "set_budget":
        response_message = handle_set_budget(entities, current_user, session)
    elif intent == "show_budget":
        response_message = handle_show_budget(entities, current_user, session)
>>>>>>> working-branch
    elif intent == "unknown":
        response_message = get_professional_response("unknown", entities)
    else:
        response_message = get_professional_response("fallback", entities)

    await save_chat_history(current_user, response_message, 'bot', session)
    return {"response": response_message}
