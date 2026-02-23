from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel.ext.asyncio.session import AsyncSession as Session
from sqlmodel import select
from pydantic import BaseModel
import csv
from pathlib import Path
import logging
from datetime import datetime

from .auth import get_current_user
from .database import get_session
from .models import ChatHistory
from .schemas import chatMessage
from .utils.entity_extractor import extract_entities, get_professional_response
from .utils.expense_parser import process_expense

# Import Services
from .services.chat_nlp import predict_intent, retrain_model_logic, CONFIDENCE_THRESHOLD
from .services.chat_handlers import (
    handle_add_expense, 
    handle_total_expenses, 
    handle_show_expenses, 
    handle_set_budget, 
    handle_show_budget,
    handle_add_income,
    save_chat_history
)

# Configure Logger
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat")

@router.get("/history")
async def get_chat_history(session: Session = Depends(get_session), current_user: int = Depends(get_current_user)):
    stmt = select(ChatHistory).where(ChatHistory.user_id == current_user).order_by(ChatHistory.timestamp)
    result = await session.execute(stmt)
    chat_history = result.scalars().all()
    return [
        { 
            "sender": c.sender, 
            "text": c.message, 
            "time": c.timestamp, 
            "data": c.data.get("expenses") if (c.data and isinstance(c.data, dict) and "expenses" in c.data) else c.data
        }
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
    logger.info(f"Chat history cleared for user {current_user}")
    return {"message": "Chat history cleared"}

class LearnRequest(BaseModel):
    text: str
    intent: str

@router.post("/learn")
async def learn_from_chat(request: LearnRequest, session: Session = Depends(get_session), current_user: int = Depends(get_current_user)):
    """Add a new training example to the dataset."""
    valid_intents = ["add_expense", "show_expenses", "total_expenses", "set_budget", "show_budget", "unknown"]
    if request.intent not in valid_intents:
         raise HTTPException(status_code=400, detail=f"Invalid intent. Must be one of {valid_intents}")

    # Append to CSV
    dataset_path = Path(__file__).parent / "ml" / "intent_dataset.csv"
    try:
        with open(dataset_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([request.text, request.intent])
        logger.info(f"New training example added: '{request.text}' -> {request.intent}")
    except Exception as e:
        logger.error(f"Failed to write to dataset: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to write to dataset: {str(e)}")
        
    return {"message": "New training example added successfully"}

@router.get("/suggestions")
async def get_chat_suggestions(q: str = Query("", min_length=1), current_user: int = Depends(get_current_user), session: Session = Depends(get_session)):
    """Provide Google-style autocomplete suggestions."""
    query = q.lower().strip()
    suggestions = []
    
    # 1. Standard Templates
    templates = [
        "Show my expenses",
        "Show expense history",
        "Show budget",
        "Check my budget status",
        "Total expenses this month",
        "How much did I spend on food?",
        "How much did I spend on travel?",
        "Set budget for food 5000",
        "Set budget for travel 2000",
        "Clear chat history"
    ]
    
    # 2. Dynamic Templates
    import re
    if re.match(r'^\d+$', query):
        suggestions.append(f"Spent {query} on food")
        suggestions.append(f"Spent {query} on travel")
        suggestions.append(f"Spent {query} on entertainment")
    
    if query.startswith(("spent", "paid", "bought", "add")):
        suggestions.append("Spent [amount] on [category]")
        suggestions.append("Paid [amount] for [item]")
    
    # 3. Dynamic from Dataset
    dataset_path = Path(__file__).parent / "ml" / "intent_dataset.csv"
    try:
        if dataset_path.exists():
            with open(dataset_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader, None) # Skip header
                for row in reader:
                    if len(row) >= 1:
                        text = row[0]
                        if query in text.lower():
                            suggestions.append(text.strip())
    except Exception as e:
        logger.error(f"Error reading dataset for suggestions: {e}")

    # 4. Personal History
    try:
        stmt = select(ChatHistory).where(
            ChatHistory.user_id == current_user,
            ChatHistory.sender == 'user'
        ).order_by(ChatHistory.timestamp.desc()).limit(50)
        
        result = await session.execute(stmt)
        history_items = result.scalars().all()
        
        history_suggestions = [h.message for h in history_items if query in h.message.lower()]
        suggestions.extend([h.strip() for h in history_suggestions])
    except Exception as e:
        logger.error(f"Error fetching history suggestions: {e}")

    # 5. Filter and Rank
    for t in templates:
        if query in t.lower():
            suggestions.append(t)
            
    unique_suggestions = list(dict.fromkeys(suggestions))
    unique_suggestions.sort()
    return {"suggestions": unique_suggestions[:10]}

@router.post("/retrain")
async def retrain_model(session: Session = Depends(get_session), current_user: int = Depends(get_current_user)):
    """Retrain the intent model with the latest dataset."""
    try:
        retrain_model_logic()
        return {"message": "Model retrained and reloaded successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")

@router.post("/message")
async def chat_endpoint(chatmessage: chatMessage, session: Session = Depends(get_session), current_user: int = Depends(get_current_user)):
    text = chatmessage.message.strip()
    
    # --- CONVERSATIONAL LEARNING / CORRECTION LOGIC ---
    lower_text = text.lower()
    if lower_text.startswith(("correction:", "learn:", "wrong, it's", "actually, it's")):
        potential_intent = lower_text.split(":")[-1].strip() if ":" in lower_text else lower_text.split("it's")[-1].strip()
        
        valid_intents = ["add_expense", "show_expenses", "total_expenses", "set_budget", "show_budget", "unknown"]
        matched_intent = next((i for i in valid_intents if i in potential_intent), None)
        
        if matched_intent:
            stmt = select(ChatHistory).where(
                ChatHistory.user_id == current_user, 
                ChatHistory.sender == 'user'
            ).order_by(ChatHistory.timestamp.desc()).limit(1)
            result = await session.execute(stmt)
            last_message = result.scalars().first()
            
            if last_message:
                learn_req = LearnRequest(text=last_message.message, intent=matched_intent)
                await learn_from_chat(learn_req, session, current_user)
                await retrain_model(session, current_user)
                
                response_msg = f"✅ Thanks! I've learned that '{last_message.message}' should be recognized as '{matched_intent}'. I've updated my model."
                await save_chat_history(current_user, text, 'user', session)
                await save_chat_history(current_user, response_msg, 'bot', session)
                return {"response": response_msg}
            else:
                response_msg = "⚠ I couldn't find a previous message to learn from."
                await save_chat_history(current_user, text, 'user', session)
                await save_chat_history(current_user, response_msg, 'bot', session)
                return {"response": response_msg}

    # Standard flow
    await save_chat_history(current_user, chatmessage.message, 'user', session)

    # 1. Extract Entities
    entities = extract_entities(text)

    # 2. Predict Intent
    try:
        result = predict_intent(text)
        probs = result["probs"]
        
        # Apply Boosts (Local logic kept here as it's part of the routing decision)
        expense_verbs = ["spent", "paid", "bought", "purchased", "went", "ate", "had", "visit","add expense","add"]
        if any(word in text.lower() for word in expense_verbs):
            probs["add_expense"] = probs.get("add_expense", 0) + 0.4
            
        if entities["amount"]:
            if entities["category"]:
                probs["add_expense"] = probs.get("add_expense", 0) + 0.2
                
        budget_keywords = ["limit", "budget", "cap", "target", "set",]
        if any(word in text.lower() for word in budget_keywords):
            if entities["amount"]:
                probs["set_budget"] = probs.get("set_budget", 0) + 0.4
            else:
                probs["set_budget"] = probs.get("set_budget", 0) + 0.2
        elif "budget" not in text.lower():
            probs["set_budget"] = probs.get("set_budget", 0) - 0.2

        if any(word in text.lower() for word in ["show", "list", "view", "total", "summary"]):
            if "budget" in text.lower():
                probs["show_budget"] = probs.get("show_budget", 0) + 0.2
            else:
                probs["show_expenses"] = probs.get("show_expenses", 0) + 0.2
                probs["total_expenses"] = probs.get("total_expenses", 0) + 0.2
        
        if any(word in text.lower() for word in ["total", "summary","sum","how much"]):
            probs["total_expenses"] = probs.get("total_expenses", 0) + 0.2      
        
        # Navigation Boost (Force Override)
        nav_keywords = ["previous", "next", "week", "month", "last"]
        if any(word in text.lower() for word in nav_keywords) and not any(word in text.lower() for word in ["add", "spent", "paid", "bought"]):
             # Force high confidence for navigation
             probs["show_expenses"] = 0.95
             # Lower others to ensure winner
             probs["unknown"] = 0.0
             probs["fallback"] = 0.0
        
        intent = max(probs, key=probs.get)
        confidence = probs[intent]
        
        if confidence < CONFIDENCE_THRESHOLD:
            intent = "fallback"
            
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        intent = "fallback"

    # 3. Route to Handler
    data_updated = False
    response_data = None
    
    if intent == "add_expense":
        # Integrate automatic extraction module
        try:
            parsed = process_expense(text)
            entities["amount"] = parsed["amount"]
            entities["category"] = parsed["category"]
        except:
            pass
        response_message, data_updated = await handle_add_expense(entities, current_user, session)
        
        # Check if income exists for current month
        now = datetime.now()
        from .models import Income
        stmt = select(Income).where(Income.user_id == current_user, Income.month == now.month, Income.year == now.year)
        income_res = await session.execute(stmt)
        if not income_res.scalars().first():
            response_message += "\n\n💡 **Tip**: To calculate your Financial Health Score, please tell me your monthly income. (e.g., 'My salary is 50000')"
            
    elif intent == "total_expenses":
        response_message = await handle_total_expenses(entities, current_user, session)
        
    elif intent == "show_expenses":
        response_message, response_data = await handle_show_expenses(entities, current_user, session)
        
    elif intent == "set_budget":
        response_message, data_updated = await handle_set_budget(entities, current_user, session)
        
    elif intent == "show_budget":
        response_message, response_data = await handle_show_budget(entities, current_user, session)
    
    elif intent == "add_income":
        response_message, data_updated = await handle_add_income(entities, current_user, session)
        
    elif intent == "unknown":
        response_message = get_professional_response("unknown", entities)
    else:
        response_message = get_professional_response("fallback", entities)
    
    await save_chat_history(current_user, response_message, 'bot', session, data=response_data)
    
    # Sanitize data for frontend (keep table compatibility)
    frontend_data = response_data
    if isinstance(response_data, dict) and "expenses" in response_data:
        frontend_data = response_data["expenses"]
        
    return {"response": response_message, "data_updated": data_updated, "data": frontend_data}
