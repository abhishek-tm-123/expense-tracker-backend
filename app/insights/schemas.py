from pydantic import BaseModel
from enum import Enum
from typing import Optional

class InsightType(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    POSITIVE = "positive"
    NEUTRAL = "neutral"

class Insight(BaseModel):
    type: InsightType
    message: str
    metric: Optional[str] = None  # e.g., "₹5000", "+15%"
    action: Optional[str] = None  # Suggested action (e.g., "Reduce dining out")
    priority: int = 0 # Higher is more important
