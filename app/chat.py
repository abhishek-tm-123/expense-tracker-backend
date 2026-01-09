import joblib
import re
import nltk
from nltk.stem import WordNetLemmatizer
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select, Session

from .auth import get_current_user
from .database import get_session
from .schemas import chatMessage
from .models import Expense, ChatHistory
from .utils.entity_extractor import extract_entities, get_professional_response

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
    print("\n\n\n",intent, confidence,"\n\n\n")
    return {
        "intent": intent,
        "confidence": confidence,
        "probs": dict(zip(intent_pipeline.classes_, probs))
    }

router = APIRouter(prefix="/chat")

def save_chat_history(user_id:int, message:str, sender:str, session:Session):   
    chat_entry = ChatHistory(user_id=user_id, message=message, sender=sender)
    session.add(chat_entry)
    session.commit()
    return chat_entry

@router.get("/history")
def get_chat_history(session: Session = Depends(get_session), current_user: int = Depends(get_current_user)):
    stmt = select(ChatHistory).where(ChatHistory.user_id == current_user).order_by(ChatHistory.timestamp)
    chat_history = session.exec(stmt).all()
    return [
        { "sender": c.sender, "text": c.message, "time": c.timestamp}
        for c in chat_history
    ]

@router.delete("/clear")
def clear_chat(session: Session = Depends(get_session), current_user: int = Depends(get_current_user)):
    stmt = select(ChatHistory).where(ChatHistory.user_id == current_user)
    chats = session.exec(stmt).all()
    for chat in chats:
        session.delete(chat)
    session.commit()
    return {"message": "Chat history cleared"}

def handle_add_expense(entities, user_id, session):
    if not entities["amount"] or not entities["category"]:
        return get_professional_response("add_expense", entities, success=False)
    
    expense = Expense(
        title=f"{entities['category'].title()} expense",
        user_id=user_id,
        amount=entities["amount"],
        category=entities["category"]
    )
    session.add(expense)
    session.commit()
    return get_professional_response("add_expense", entities, success=True)

def handle_total_expenses(entities, user_id, session):
    stmt = select(Expense).where(Expense.user_id == user_id)
    if entities["start_date"] and entities["end_date"]:
        stmt = stmt.where(Expense.created_at >= entities["start_date"], Expense.created_at <= entities["end_date"])
    
    expenses = session.exec(stmt).all()
    total = sum(e.amount for e in expenses)
    return get_professional_response("total_expenses", entities, data={"total": total})

def handle_show_expenses(entities, user_id, session):
    stmt = select(Expense).where(Expense.user_id == user_id)
    if entities["start_date"] and entities["end_date"]:
        stmt = stmt.where(Expense.created_at >= entities["start_date"], Expense.created_at <= entities["end_date"])
    
    expenses = session.exec(stmt).all()
    return get_professional_response("show_expenses", entities, data={"expenses": expenses})

@router.post("/message")
def chat_endpoint(chatmessage: chatMessage, session: Session = Depends(get_session), current_user: int = Depends(get_current_user)):
    text = chatmessage.message.strip()
    save_chat_history(current_user, chatmessage.message, 'user', session)

    # 1. Extract Entities (used for boosting and processing)
    entities = extract_entities(text)

    # 2. Predict Intent
    try:
        result = predict_intent(text)
        intent = result["intent"]
        confidence = result["confidence"]
        
        # --- HYBRID BOOSTING LOGIC ---
        # If we found critical entities, we boost the confidence of the corresponding intent
        if intent == "add_expense" and entities["amount"] and entities["category"]:
            confidence += 0.3
        elif intent in ["total_expenses", "show_expenses"] and entities["date_label"] != "overall":
            confidence += 0.2
            
        if confidence < CONFIDENCE_THRESHOLD:
            intent = "fallback"
            
        print(f"DEBUG: Intent={intent}, Final Confidence={confidence:.2f}")
    except Exception as e:
        print(f"DEBUG: Prediction error: {e}")
        intent = "fallback"

    # 3. Route to Handler
    if intent == "add_expense":
        response_message = handle_add_expense(entities, current_user, session)
    elif intent == "total_expenses":
        response_message = handle_total_expenses(entities, current_user, session)
    elif intent == "show_expenses":
        response_message = handle_show_expenses(entities, current_user, session)
    elif intent == "unknown":
        response_message = get_professional_response("unknown", entities)
    else:
        response_message = get_professional_response("fallback", entities)

    save_chat_history(current_user, response_message, 'bot', session)
    return {"response": response_message}
