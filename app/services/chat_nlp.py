import logging
import sys
from pathlib import Path

# Configure Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global variables for lazy loading
_intent_pipeline = None
_lemmatizer = None

def get_intent_pipeline():
    """Lazy loader for the ML intent model."""
    global _intent_pipeline
    if _intent_pipeline is not None:
        return _intent_pipeline
    
    import joblib
    model_path = Path(__file__).parent.parent / "ml" / "intent_pipeline_v1.pkl"
    try:
        _intent_pipeline = joblib.load(model_path)
        logger.info("ML intent model loaded successfully")
    except FileNotFoundError:
        logger.warning("ML model not found. Using rule-based intent detection.")
    except Exception as e:
        logger.warning(f"Could not load ML model: {e}. Using rule-based intent detection.")
    
    return _intent_pipeline

def get_lemmatizer():
    """Lazy loader for the NLTK lemmatizer."""
    global _lemmatizer
    if _lemmatizer is not None:
        return _lemmatizer
    
    import nltk
    from nltk.stem import WordNetLemmatizer
    try:
        _lemmatizer = WordNetLemmatizer()
        _lemmatizer.lemmatize("test")
    except LookupError:
        logger.info("Downloading NLTK resources...")
        nltk.download('wordnet', quiet=True)
        nltk.download('omw-1.4', quiet=True)
        _lemmatizer = WordNetLemmatizer()
    
    return _lemmatizer

CONFIDENCE_THRESHOLD = 0.5

def preprocess_text(text: str) -> str:
    """Preprocess text with lemmatization for better intent matching."""
    lemmatizer = get_lemmatizer()
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
    if any(word in text_lower for word in ["add expense","spent", "paid", "bought", "purchased"]):
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
    intent_pipeline = get_intent_pipeline()
    
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
        logger.error(f"ML prediction failed: {e}, using rule-based fallback")
        return predict_intent_rule_based(text)

