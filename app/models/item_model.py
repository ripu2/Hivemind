from dataclasses import dataclass
from typing import Optional


@dataclass
class Item:
    id: int
    name: str
    description: Optional[str] = None
