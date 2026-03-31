from app.repositories.item_repository import ItemRepository
from app.schemas.item_schema import ItemCreate, ItemRead
from typing import Optional


class ItemService:
    def __init__(self, repository: Optional[ItemRepository] = None) -> None:
        self.repository = repository or ItemRepository()

    def list_items(self) -> list[ItemRead]:
        return [ItemRead(**item.__dict__) for item in self.repository.list_items()]

    def get_item(self, item_id: int) -> Optional[ItemRead]:
        item = self.repository.get_by_id(item_id)
        if item is None:
            return None
        return ItemRead(**item.__dict__)

    def create_item(self, payload: ItemCreate) -> ItemRead:
        item = self.repository.create(name=payload.name, description=payload.description)
        return ItemRead(**item.__dict__)
