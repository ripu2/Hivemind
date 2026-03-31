from pinecone import Pinecone, ServerlessSpec
from app import config
from app.logger import get_logger

log = get_logger(__name__)

_pc: Pinecone | None = None


def connect() -> None:
    global _pc
    _pc = Pinecone(api_key=config.PINECONE_API_KEY)
    existing = [i.name for i in _pc.list_indexes()]
    if config.PINECONE_INDEX_NAME not in existing:
        _pc.create_index(
            name=config.PINECONE_INDEX_NAME,
            dimension=1536,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        log.info("Created Pinecone index '%s'", config.PINECONE_INDEX_NAME)
    else:
        log.info("Connected to Pinecone index '%s'", config.PINECONE_INDEX_NAME)


def disconnect() -> None:
    global _pc
    _pc = None
    log.info("Pinecone client released")


def get_client() -> Pinecone:
    if _pc is None:
        raise RuntimeError("Pinecone is not initialised")
    return _pc
