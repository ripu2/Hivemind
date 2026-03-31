from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

from app import config
from app.logger import get_logger
from app.repositories.crawl_index_repository import CrawlIndexRepository
from app.repositories.conversation_repository import ConversationRepository

log = get_logger(__name__)

_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are an expert technical assistant. Your job is to give complete, "
        "structured answers based strictly on the retrieved context below.\n\n"
        "How to structure your answer:\n"
        "- Start with a one-sentence summary of what the answer covers.\n"
        "- If there are prerequisites, permissions, or prior setup needed, list them first under a '## Prerequisites' section.\n"
        "- Break the answer into clear sections with markdown headers (##).\n"
        "- For any procedure or how-to, list every step in order under '## Steps', numbered, with no steps skipped.\n"
        "- Include exact values, field names, button labels, or code snippets from the context — do not paraphrase them.\n"
        "- If there are gotchas, warnings, or common mistakes mentioned in the context, include them under '## Notes'.\n"
        "- End with a one-line summary of what was accomplished.\n\n"
        "Hard rules:\n"
        "1. Only use information present in the context. Do not add outside knowledge.\n"
        "2. If the context does not contain enough information, say exactly: "
        "'I don't have enough information in the indexed documents to answer that fully.' "
        "Then list what partial information you do have.\n"
        "3. Never invent URLs, file paths, config keys, or code not present in the context.\n"
        "4. If the user refers to something from earlier in the conversation, use the chat "
        "history to resolve what they mean — but ground the answer in the context.\n\n"
        "Retrieved context:\n"
        "-----\n"
        "{context}\n"
        "-----",
    ),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{question}"),
])


class QueryService:
    def __init__(self) -> None:
        self.embeddings = OpenAIEmbeddings(api_key=config.OPENAI_API_KEY)
        self.llm = ChatOpenAI(api_key=config.OPENAI_API_KEY, model="gpt-4o-mini", temperature=0)
        self.crawl_index_repo = CrawlIndexRepository()
        self.conversation_repo = ConversationRepository()

    def _search_namespaces(self, question: str, namespaces: list[str], k: int = 5):
        """Search across namespaces in parallel, return top-k by score."""
        per_ns = max(k, 3)

        def _query_ns(ns: str):
            vs = PineconeVectorStore(
                index_name=config.PINECONE_INDEX_NAME,
                embedding=self.embeddings,
                namespace=ns,
            )
            return vs.similarity_search_with_score(question, k=per_ns)

        scored = []
        with ThreadPoolExecutor(max_workers=min(len(namespaces), 5)) as pool:
            futures = {pool.submit(_query_ns, ns): ns for ns in namespaces}
            for future in as_completed(futures):
                try:
                    scored.extend(future.result())
                except Exception:
                    pass  # one namespace failing shouldn't kill the whole query

        scored.sort(key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in scored[:k]]

    def query(self, question: str, url: str | None = None, conversation_id: str | None = None) -> dict:
        # ── Resolve namespace(s) ───────────────────────────────────────────
        namespaces: list[str] = []
        namespace_label: str | None = None

        if url:
            record = self.crawl_index_repo.get_by_url(url)
            if record is None:
                return {
                    "answer": f"'{url}' has not been indexed yet. Please crawl it first.",
                    "sources": [],
                    "namespace": None,
                    "conversation_id": conversation_id or self.conversation_repo.create_conversation(),
                }
            namespaces = [record.pinecone_namespace]
            namespace_label = record.pinecone_namespace
        else:
            all_records = self.crawl_index_repo.list_all()
            namespaces = [r.pinecone_namespace for r in all_records]
            if not namespaces:
                return {
                    "answer": "No documents have been indexed yet. Please crawl a website first.",
                    "sources": [],
                    "namespace": None,
                    "conversation_id": conversation_id or self.conversation_repo.create_conversation(),
                }

        # ── Resolve / create conversation ──────────────────────────────────
        if conversation_id and self.conversation_repo.conversation_exists(conversation_id):
            messages = self.conversation_repo.get_messages(conversation_id)
        else:
            conversation_id = self.conversation_repo.create_conversation()
            messages = []

        # ── Retrieve relevant chunks from Pinecone ─────────────────────────
        docs = self._search_namespaces(question, namespaces)

        context = "\n\n---\n\n".join(doc.page_content for doc in docs) if docs else ""
        sources = list({doc.metadata.get("source", "") for doc in docs if doc.metadata.get("source")})

        # ── Build history for the prompt ───────────────────────────────────
        history = []
        for msg in messages:
            if msg.role == "human":
                history.append(HumanMessage(content=msg.content))
            else:
                history.append(AIMessage(content=msg.content))

        # ── Call LLM ───────────────────────────────────────────────────────
        chain = _PROMPT | self.llm
        response = chain.invoke({"context": context, "history": history, "question": question})
        answer = response.content

        # ── Persist turn ───────────────────────────────────────────────────
        self.conversation_repo.add_message(conversation_id, "human", question)
        self.conversation_repo.add_message(conversation_id, "ai", answer)

        return {
            "answer": answer,
            "sources": sources,
            "namespace": namespace_label,
            "conversation_id": conversation_id,
        }
