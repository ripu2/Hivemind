from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from app import config


class RetrievalService:
    def __init__(self) -> None:
        self.embeddings = OpenAIEmbeddings(api_key=config.OPENAI_API_KEY)
        self.vector_store = PineconeVectorStore(
            index_name=config.PINECONE_INDEX_NAME,
            embedding=self.embeddings,
        )

    def retrieve(self, query: str, k: int = 5) -> list[str]:
        docs = self.vector_store.similarity_search(query, k=k)
        return [doc.page_content for doc in docs]
