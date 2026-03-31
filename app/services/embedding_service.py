from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from app import config


class EmbeddingService:
    def __init__(self) -> None:
        self.embeddings = OpenAIEmbeddings(api_key=config.OPENAI_API_KEY)

    def load_files_from_directory(self, path: str, glob: str = "**/*.txt") -> list[Document]:
        loader = DirectoryLoader(
            path,
            glob=glob,
            show_progress=True,
            loader_kwargs={"encoding": "utf-8"},
            loader_cls=TextLoader,
        )
        try:
            return loader.load()
        except Exception as e:
            print(f"Error loading files from {path}: {e}")
            return []

    def split_documents(self, documents: list[Document]) -> list[Document]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
        )
        return splitter.split_documents(documents)

    def embed_and_store(self, documents: list[Document], namespace: str) -> int:
        chunks = self.split_documents(documents)
        PineconeVectorStore.from_documents(
            chunks,
            self.embeddings,
            index_name=config.PINECONE_INDEX_NAME,
            namespace=namespace,
        )
        return len(chunks)

    def embed_directory(self, path: str, namespace: str, glob: str = "**/*.txt") -> int:
        documents = self.load_files_from_directory(path, glob)
        if not documents:
            return 0
        return self.embed_and_store(documents, namespace=namespace)
