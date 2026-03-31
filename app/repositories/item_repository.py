from app.models.item_model import Item
from typing import Optional


class ItemRepository:
    def __init__(self) -> None:
        self._items: list[Item] = []
        self._next_id = 1

    def list_items(self) -> list[Item]:
        return self._items

    def get_by_id(self, item_id: int) -> Optional[Item]:
        for item in self._items:
            if item.id == item_id:
                return item
        return None

    def create(self, name: str, description: Optional[str]) -> Item:
        item = Item(id=self._next_id, name=name, description=description)
        self._items.append(item)
        self._next_id += 1
        return item
