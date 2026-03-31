import json
import threading

from langchain_openai import ChatOpenAI

from app import config
from app.logger import get_logger
from app.repositories.faq_repository import FaqRepository

log = get_logger(__name__)

_THEME_PROMPT = """You are analyzing user queries to build a FAQ for a documentation assistant.

Here are the most recent user queries (newest first):
{queries}

Task:
1. Identify the {limit} most distinct, commonly occurring topics across these queries.
2. For each topic, write one clear, well-phrased FAQ question that best captures what users are asking.
3. Also return the approximate count of queries that relate to each topic.

Return ONLY a valid JSON array, no extra text:
[
  {{"question": "How do I ...?", "frequency": 12}},
  ...
]"""


class FaqService:
    def __init__(self) -> None:
        self.llm = ChatOpenAI(api_key=config.OPENAI_API_KEY, model="gpt-4o-mini", temperature=0)
        self.faq_repo = FaqRepository()

    def get_faqs(self):
        return self.faq_repo.get_faqs()

    def regenerate(self) -> int:
        """Analyse query logs, generate up to 5 FAQs with answers. Returns count generated."""
        from app.services.query_service import QueryService  # avoids import-time circular dep

        questions_raw = self.faq_repo.get_recent_questions(limit=200)
        if len(questions_raw) < 3:
            log.info("FAQ regeneration skipped: not enough queries (%d)", len(questions_raw))
            return 0

        query_list = "\n".join(f"- {q}" for q in questions_raw)
        prompt = _THEME_PROMPT.format(queries=query_list, limit=5)

        try:
            response = self.llm.invoke(prompt)
            raw = response.content.strip()
            # Strip markdown code fences if LLM wraps output
            if raw.startswith("```"):
                raw = "\n".join(raw.split("\n")[1:]).rstrip("`").strip()
            themes = json.loads(raw)
            if not isinstance(themes, list):
                raise ValueError("Expected a JSON array")
        except Exception as e:
            log.error("FAQ theme extraction failed: %s", e)
            return 0

        qs = QueryService()
        faqs: list[tuple[str, str, int]] = []

        for item in themes[:5]:
            question = item.get("question", "").strip()
            frequency = int(item.get("frequency", 1))
            if not question:
                continue
            try:
                result = qs.query(question)
                faqs.append((question, result["answer"], frequency))
            except Exception as e:
                log.warning("FAQ answer generation failed for '%s': %s", question, e)

        if faqs:
            try:
                self.faq_repo.replace_faqs(faqs)
                log.info("FAQs regenerated: %d items", len(faqs))
            except Exception as e:
                log.error("FAQ DB replace failed: %s", e)
                return 0

        return len(faqs)

    def regenerate_async(self) -> None:
        def _run():
            try:
                self.regenerate()
            except Exception as e:
                log.error("Unhandled exception in FAQ regeneration thread: %s", e)

        threading.Thread(target=_run, daemon=True).start()
