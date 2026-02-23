import re

def extract_amount(text: str) -> float:
    # Pre-process text to handle 'k' notation and clean numeric strings
    text = text.lower().replace(",", "")
    
    # regex to find numbers potentially followed by 'k'
    # handles cases like 40k, 40 k, 40.5k
    patterns = [
        r"(?:rs|₹|income|salary|earn|paid|spent|cost|for)\s?(\d+(?:\.\d+)?)\s?(k)?",
        r"(\d+(?:\.\d+)?)\s?(k)?\s?(?:rs|rupees|income|salary|earnings|per month)",
        r"(\d+(?:\.\d+)?)\s?(k)?"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            val = float(match.group(1))
            if match.group(2) == 'k':
                val *= 1000
            return val
            
    raise ValueError("Amount not found in text")

def detect_category(text: str) -> str:
    keyword_map = {
        "food": [
            "pizza", "burger", "meal", "lunch", "dinner", "restaurant", "hotel", 
            "swiggy", "zomato", "biryani", "thali", "dosa", "idli", "paneer", 
            "blinkit", "zepto", "bigbasket", "milk", "grocery","food",
        ],
        "snacks": ["chai", "coffee", "chips", "biscuit", "maggi", "momos", "samosa", "chaat", "juice","snacks"],
        "travel": ["bus", "train", "taxi", "uber", "ola", "flight", "rickshaw", "auto", "metro", "rapido", "irctc","travel"],
        "fuel": ["petrol", "diesel", "fuel", "cng", "shell", "iocl", "bpcl","fuel"],
        "entertainment": ["movie", "netflix", "prime", "hotstar", "pvr", "inox", "bookmyshow", "concert", "match","entertainment","games","sports"],
        "health": ["doctor", "medicine", "hospital", "clinic", "pharmacy", "apollo", "1mg", "pharmeasy","health"],
        "shopping": ["shirt", "shoes", "clothes", "amazon", "flipkart", "myntra", "ajio", "meesho", "mall","shopping"],
        "rent": ["rent", "electricity", "water", "gas", "indane", "bijli","rent"]
    }
    
    scores = {cat: 0 for cat in keyword_map}
    text_lower = text.lower()
    
    for category, keywords in keyword_map.items():
        for keyword in keywords:
            if keyword in text_lower:
                scores[category] += 1
                
    max_score = 0
    detected_category = "others"
    
    for category, score in scores.items():
        if score > max_score:
            max_score = score
            detected_category = category
            
    return detected_category

def process_expense(text: str) -> dict:
    amount = extract_amount(text)
    category = detect_category(text)
    return {
        "amount": amount,
        "category": category,
        "message": f"{int(amount) if amount.is_integer() else amount} rs added under {category}"
    }
