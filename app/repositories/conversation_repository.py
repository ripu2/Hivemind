from app import database
from app.models.conversation_model import ConversationMessage


class ConversationRepository:
    def create_conversation(self) -> str:
        """Creates a new conversation and returns its UUID."""
        conn = database.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO conversations DEFAULT VALUES RETURNING id")
                conversation_id = str(cur.fetchone()[0])
            conn.commit()
            return conversation_id
        finally:
            database.put_conn(conn)

    def conversation_exists(self, conversation_id: str) -> bool:
        conn = database.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM conversations WHERE id = %s", (conversation_id,))
                return cur.fetchone() is not None
        finally:
            database.put_conn(conn)

    def get_messages(self, conversation_id: str) -> list[ConversationMessage]:
        conn = database.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, conversation_id, role, content, created_at "
                    "FROM conversation_messages "
                    "WHERE conversation_id = %s ORDER BY created_at ASC",
                    (conversation_id,),
                )
                return [
                    ConversationMessage(
                        id=r[0],
                        conversation_id=str(r[1]),
                        role=r[2],
                        content=r[3],
                        created_at=r[4],
                    )
                    for r in cur.fetchall()
                ]
        finally:
            database.put_conn(conn)

    def add_message(self, conversation_id: str, role: str, content: str) -> None:
        conn = database.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO conversation_messages (conversation_id, role, content) "
                    "VALUES (%s, %s, %s)",
                    (conversation_id, role, content),
                )
            conn.commit()
        finally:
            database.put_conn(conn)
