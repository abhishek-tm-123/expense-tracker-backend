import re
from fastapi import APIRouter,Depends,HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession as Session
from .auth import get_current_user
from .database import get_session
from .schemas import chatMessage,BudgetCreate,BudgetRead
from .models import Expense,ChatHistory
from .budget import create_or_update_budget

import joblib
from pathlib import Path
from .utils.date_parser import parse_date_range

from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
ML_DIR = BASE_DIR / "ml"

# Load the trained model and vectorizer
intent_model = joblib.load(ML_DIR / "intent_pipeline_v1.pkl")
vectorizer = joblib.load(ML_DIR / "vectorizer.pkl")

def predict_intent(text: str) -> str:
    vec = vectorizer.transform([text])
    probs = intent_model.predict_proba(vec)[0]
    confidence = max(probs)
    intent = intent_model.classes_[probs.argmax()]
    print(f"\n\n\nPredicted intent: {intent}\n with confidence {confidence}\n prob {probs}\n\n\n")
    if confidence < 0.3:
        return "unknown"
    return intent

router = APIRouter(prefix="/chat")

async def save_chat_history(user_id:int,message:str,sender:str,session:Session):   
    chat_entry = ChatHistory(
        user_id=user_id,
        message=message,
        sender=sender
    )
    session.add(chat_entry)
    await session.commit()
    return chat_entry

@router.get("/history")
async def get_chat_history(session: Session = Depends(get_session), current_user: int = Depends(get_current_user)):
    stmt = select(ChatHistory).where(ChatHistory.user_id == current_user).order_by(ChatHistory.timestamp)
    result = await session.execute(stmt)
    chat_history = result.scalars().all()
    return [
        { "sender": c.sender, "text": c.message ,"time":c.timestamp}
        for c in chat_history
    ]

@router.delete("/clear")
async def clear_chat(
    session: Session = Depends(get_session),
    current_user: int = Depends(get_current_user)
):
    stmt = select(ChatHistory).where(ChatHistory.user_id == current_user)
    result = await session.execute(stmt)
    chats = result.scalars().all()

    for chat in chats:
        await session.delete(chat)

    await session.commit()

    return {"message": "Chat history cleared"}


@router.post("/message")
async def chat_endpoint(chatmessage: chatMessage, session: Session = Depends(get_session), current_user: int = Depends(get_current_user)):
    # rule based chat bot system

    text = chatmessage.message.lower().strip()

    intent = predict_intent(text)

    await save_chat_history(current_user, chatmessage.message, 'user', session)

   
    if intent == "add_expense":
        # entity extraction (still rule-based)
        amount_match = re.search(r"\d+", text)
        category_match = re.search(r"(food|travel|rent|snacks|shopping|fuel)", text)
        if not amount_match or not category_match:
            response_message = "Please provide both amount and category to add an expense."
            await save_chat_history(current_user, response_message, 'bot', session)
        else:
            amount = int(amount_match.group())
            category = category_match.group()

            # db operation to add expense
            expense = Expense(
                title=f"{category} expense",
                user_id=current_user,
                amount=amount,
                category=category
                
            )
            session.add(expense)
            await session.commit()
            response_message = f"Expense of {amount} in category '{category}' added successfully."
            await save_chat_history(current_user, response_message, 'bot', session)
            return {"response": response_message}
    
    if intent == "set_budget":
        response_message = "called set budget"
        await save_chat_history(current_user, response_message, 'bot', session)
        return {"response": response_message}

    if intent == "total_expenses":

        start_date, end_date,label = parse_date_range(text)
        
        # db operation to calculate total expenses
        stmt = select(Expense).where(Expense.user_id == current_user)
        if start_date and end_date:
            stmt = stmt.where(
                Expense.created_at >= start_date,
                Expense.created_at <= end_date
            )
        result = await session.execute(stmt)
        expenses = result.scalars().all()
        total_expenses = sum(e.amount for e in expenses)

        
        response_message = f"Your total expenses are on {label} is {total_expenses}."
        await save_chat_history(current_user, response_message, 'bot', session)
        return {"response": response_message}

    if intent == "show_expenses":
        start_date, end_date,label = parse_date_range(text)
        # db operation to fetch all expenses
        stmt = select(Expense).where(Expense.user_id == current_user)
        if start_date and end_date:
            stmt = stmt.where(
                Expense.created_at >= start_date,
                Expense.created_at <= end_date
            )
        result = await session.execute(stmt)
        expenses = result.scalars().all()

        if not expenses:
            return {"response": "You have no recorded expenses."}
        lines = [
            f"₹{e.amount} - {e.category.title()} - {e.created_at.date()}"
            for e in expenses
        ]
        expenses = "\n".join(lines)
        response_message = f"Your expenses {label}:\n{expenses}"
        await save_chat_history(current_user, response_message, 'bot', session)
        return {"response": response_message,}
    
    if intent == "unknown":
        response_message = "unknown"
        await save_chat_history(current_user, response_message, 'bot', session)
        return {"response": response_message}
    
    
    
    response_message = "I'm sorry, I didn't understand that. Please use commands like 'add expense <amount> <category>', 'total', or 'show'."
    
    await save_chat_history(current_user, response_message, 'bot', session)
    return {"response": response_message}

