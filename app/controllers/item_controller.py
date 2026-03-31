from fastapi import APIRouter, HTTPException

from app.schemas.item_schema import ItemCreate, ItemRead
from app.services.item_service import ItemService


router = APIRouter(tags=["items"])
item_service = ItemService()


@router.get("/items", response_model=list[ItemRead])
async def list_items() -> list[ItemRead]:
    return item_service.list_items()


@router.get("/items/{item_id}", response_model=ItemRead)
async def get_item(item_id: int) -> ItemRead:
    item = item_service.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.post("/items", response_model=ItemRead, status_code=201)
async def create_item(payload: ItemCreate) -> ItemRead:
    return item_service.create_item(payload)
