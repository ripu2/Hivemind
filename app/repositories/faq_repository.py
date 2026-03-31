from app import database
from app.models.faq_model import Faq

FAQ_LIMIT = 5
REGENERATE_EVERY = 10


class FaqRepository:
    def get_faqs(self) -> list[Faq]:
        conn = database.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, question, answer, frequency, generated_at "
                    "FROM faqs ORDER BY frequency DESC, generated_at DESC"
                )
                return [
                    Faq(id=r[0], question=r[1], answer=r[2], frequency=r[3], generated_at=r[4])
                    for r in cur.fetchall()
                ]
        finally:
            database.put_conn(conn)

    def replace_faqs(self, faqs: list[tuple[str, str, int]]) -> None:
        """Atomically replace all FAQs. Rolls back if anything fails so old FAQs stay visible."""
        conn = database.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM faqs")
                for question, answer, frequency in faqs[:FAQ_LIMIT]:
                    cur.execute(
                        "INSERT INTO faqs (question, answer, frequency) VALUES (%s, %s, %s)",
                        (question, answer, frequency),
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            database.put_conn(conn)

    def log_query(self, question: str, conversation_id: str | None) -> int:
        """Logs a query and returns the total query count."""
        conn = database.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO query_logs (question, conversation_id) VALUES (%s, %s)",
                    (question, conversation_id),
                )
                cur.execute("SELECT COUNT(*) FROM query_logs")
                count = cur.fetchone()[0]
            conn.commit()
            return count
        except Exception:
            conn.rollback()
            raise
        finally:
            database.put_conn(conn)

    def get_recent_questions(self, limit: int = 200) -> list[str]:
        conn = database.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT question FROM query_logs ORDER BY asked_at DESC LIMIT %s",
                    (limit,),
                )
                return [r[0] for r in cur.fetchall()]
        finally:
            database.put_conn(conn)

    def should_regenerate(self, current_count: int) -> bool:
        return current_count % REGENERATE_EVERY == 0
