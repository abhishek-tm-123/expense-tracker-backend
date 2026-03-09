from pydantic import BaseModel
from enum import Enum
from typing import Optional, Dict

class InsightType(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    STREAK = "streak"
    MILESTONE = "milestone"

class Insight(BaseModel):
    type: InsightType
    message: str
    metric: Optional[str] = None  # e.g., "₹5000", "+15%"
    action: Optional[str] = None  # Suggested action
    priority: int = 0             # Higher is more important
    metadata: Optional[Dict] = None # For frontend extras (e.g., trend: "up")
