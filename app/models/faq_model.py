from dataclasses import dataclass
from datetime import datetime


@dataclass
class Faq:
    id: int
    question: str
    answer: str
    frequency: int
    generated_at: datetime
