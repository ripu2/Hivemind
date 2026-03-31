from dataclasses import dataclass
from datetime import datetime


@dataclass
class ConversationMessage:
    id: int
    conversation_id: str
    role: str  # 'human' | 'ai'
    content: str
    created_at: datetime
