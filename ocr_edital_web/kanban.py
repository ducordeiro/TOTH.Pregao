import re
import sqlite3
from datetime import datetime
from contextlib import closing
from urllib.parse import urlparse

DEFAULT_COLUMNS = (
    "BLL", "BNC", "ComprasBR", "Licitações-e", "Licitanet", "Licita PP",
    "Licitar Digital", "NovoBBMNet", "Portal de Compras Públicas",
    "Portal de Compras RS", "SISLOG",
)

FIELDS = (
    "portal", "position_number", "modality", "agency_name", "notice_number", "uasg",
    "pncp_control_number", "opening_at", "critical_deadline",
    "internal_identifier", "title", "object_description", "phase_status",
    "priority", "pending_documents", "estimated_value", "responsible",
    "next_review_at", "notes", "source_link",
)


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def connect(database_path):
    connection = sqlite3.connect(database_path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize(database_path):
    now = now_iso()
    with closing(connect(database_path)) as connection:
        with connection:
            connection.executescript("""
            CREATE TABLE IF NOT EXISTS kanban_columns (
                id INTEGER PRIMARY KEY, user_id TEXT NOT NULL DEFAULT 'local',
                name TEXT NOT NULL, position INTEGER NOT NULL,
                color TEXT NOT NULL DEFAULT '#E8F1FB',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(user_id, name), UNIQUE(user_id, position));
            CREATE TABLE IF NOT EXISTS proposals (
                id INTEGER PRIMARY KEY, user_id TEXT NOT NULL DEFAULT 'local',
                column_id INTEGER NOT NULL REFERENCES kanban_columns(id) ON DELETE RESTRICT,
                portal TEXT NOT NULL, position_number INTEGER, modality TEXT NOT NULL DEFAULT '',
                agency_name TEXT NOT NULL DEFAULT '', notice_number TEXT NOT NULL DEFAULT '',
                uasg TEXT NOT NULL DEFAULT '', pncp_control_number TEXT NOT NULL DEFAULT '',
                opening_at TEXT NOT NULL DEFAULT '', critical_deadline TEXT NOT NULL DEFAULT '',
                internal_identifier TEXT NOT NULL DEFAULT '', title TEXT NOT NULL,
                object_description TEXT NOT NULL DEFAULT '', phase_status TEXT NOT NULL DEFAULT '',
                priority TEXT NOT NULL DEFAULT 'normal', pending_documents TEXT NOT NULL DEFAULT '',
                estimated_value TEXT NOT NULL DEFAULT '', responsible TEXT NOT NULL DEFAULT '',
                next_review_at TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
                source_link TEXT NOT NULL DEFAULT '', source_last_checked_at TEXT NOT NULL DEFAULT '',
                source_last_updated_at TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, portal, title, notice_number, uasg));
            CREATE TABLE IF NOT EXISTS proposal_stage_history (
                id INTEGER PRIMARY KEY, user_id TEXT NOT NULL DEFAULT 'local',
                proposal_id INTEGER NOT NULL REFERENCES proposals(id) ON DELETE CASCADE,
                from_column_id INTEGER REFERENCES kanban_columns(id) ON DELETE SET NULL,
                to_column_id INTEGER NOT NULL REFERENCES kanban_columns(id) ON DELETE RESTRICT,
                moved_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_proposals_column ON proposals(user_id, column_id, updated_at);
            CREATE INDEX IF NOT EXISTS idx_proposal_history ON proposal_stage_history(proposal_id, moved_at);
            """)
            proposal_columns = {row[1] for row in connection.execute("PRAGMA table_info(proposals)")}
            if "position_number" not in proposal_columns:
                connection.execute("ALTER TABLE proposals ADD COLUMN position_number INTEGER")
            if "business_id" not in proposal_columns:
                connection.execute("ALTER TABLE proposals ADD COLUMN business_id INTEGER")
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_proposals_business "
                "ON proposals(user_id, business_id) WHERE business_id IS NOT NULL"
            )
            for position, name in enumerate(DEFAULT_COLUMNS, 1):
                connection.execute(
                    "INSERT OR IGNORE INTO kanban_columns(user_id,name,position,created_at,updated_at) VALUES('local',?,?,?,?)",
                    (name, position, now, now),
                )
    
    
def row_dict(row):
    return dict(row) if row else None


def board(database_path):
    initialize(database_path)
    with closing(connect(database_path)) as connection:
        with connection:
            columns = [row_dict(row) for row in connection.execute(
                "SELECT * FROM kanban_columns WHERE user_id='local' ORDER BY position,id"
            )]
            proposals = [row_dict(row) for row in connection.execute(
                "SELECT * FROM proposals WHERE user_id='local' ORDER BY column_id, position_number IS NULL, position_number ASC, title COLLATE NOCASE, id"
            )]
        return {"columns": columns, "proposals": proposals, "sync_status": "offline"}
    
    
def clean_name(value):
    value = " ".join(str(value or "").split())
    if not value or len(value) > 80:
        raise ValueError("Informe um nome de coluna com até 80 caracteres.")
    return value


def create_column(database_path, payload):
    initialize(database_path)
    name, now = clean_name(payload.get("name")), now_iso()
    try:
        with closing(connect(database_path)) as connection:
            with connection:
                position = connection.execute(
                    "SELECT COALESCE(MAX(position),0)+1 FROM kanban_columns WHERE user_id='local'"
                ).fetchone()[0]
                cursor = connection.execute(
                    "INSERT INTO kanban_columns(user_id,name,position,created_at,updated_at) VALUES('local',?,?,?,?)",
                    (name, position, now, now),
                )
                row = connection.execute("SELECT * FROM kanban_columns WHERE id=?", (cursor.lastrowid,)).fetchone()
            return row_dict(row)
    except sqlite3.IntegrityError as exc:
        raise ValueError("Já existe uma coluna com este nome.") from exc


def ensure_column(database_path, name):
    """Return a portal column, creating it when the detected portal is new."""
    initialize(database_path)
    name, now = clean_name(name), now_iso()
    with closing(connect(database_path)) as connection:
        with connection:
            row = connection.execute(
                "SELECT * FROM kanban_columns WHERE user_id='local' AND lower(name)=lower(?)", (name,),
            ).fetchone()
            if row:
                return row_dict(row)
            position = connection.execute(
                "SELECT COALESCE(MAX(position),0)+1 FROM kanban_columns WHERE user_id='local'"
            ).fetchone()[0]
            cursor = connection.execute(
                "INSERT INTO kanban_columns(user_id,name,position,created_at,updated_at) VALUES('local',?,?,?,?)",
                (name, position, now, now),
            )
            return row_dict(connection.execute(
                "SELECT * FROM kanban_columns WHERE id=?", (cursor.lastrowid,)
            ).fetchone())


def update_column(database_path, column_id, payload):
    initialize(database_path)
    with closing(connect(database_path)) as connection:
        with connection:
            row = connection.execute("SELECT * FROM kanban_columns WHERE id=?", (column_id,)).fetchone()
            if not row:
                raise FileNotFoundError("Coluna não encontrada.")
            name = clean_name(payload.get("name", row["name"]))
            direction = payload.get("direction")
            if direction in {"left", "right"}:
                operator, order = ("<", "DESC") if direction == "left" else (">", "ASC")
                other = connection.execute(
                    f"SELECT * FROM kanban_columns WHERE user_id='local' AND position {operator} ? ORDER BY position {order} LIMIT 1",
                    (row["position"],),
                ).fetchone()
                if other:
                    temporary = -int(column_id)
                    connection.execute("UPDATE kanban_columns SET position=? WHERE id=?", (temporary, column_id))
                    connection.execute("UPDATE kanban_columns SET position=? WHERE id=?", (row["position"], other["id"]))
                    connection.execute("UPDATE kanban_columns SET position=? WHERE id=?", (other["position"], column_id))
            connection.execute("UPDATE kanban_columns SET name=?,updated_at=? WHERE id=?", (name, now_iso(), column_id))
            return row_dict(connection.execute("SELECT * FROM kanban_columns WHERE id=?", (column_id,)).fetchone())
    
    
def delete_column(database_path, column_id):
    initialize(database_path)
    with closing(connect(database_path)) as connection:
        with connection:
            count = connection.execute("SELECT COUNT(*) FROM proposals WHERE column_id=?", (column_id,)).fetchone()[0]
            if count:
                raise ValueError("Mova os cartões antes de excluir esta coluna.")
            cursor = connection.execute("DELETE FROM kanban_columns WHERE id=?", (column_id,))
            if not cursor.rowcount:
                raise FileNotFoundError("Coluna não encontrada.")
    
    
def delete_proposal(database_path, proposal_id):
    initialize(database_path)
    with closing(connect(database_path)) as connection:
        with connection:
            row = connection.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
            if not row:
                raise FileNotFoundError("Cartão não encontrado.")
            connection.execute("DELETE FROM proposal_stage_history WHERE proposal_id=?", (proposal_id,))
            connection.execute("DELETE FROM proposals WHERE id=?", (proposal_id,))
            return row_dict(row)
    
    
def validated_proposal(payload):
    data = {field: str(payload.get(field) or "").strip() for field in FIELDS}
    if data["position_number"]:
        if not data["position_number"].isdigit() or int(data["position_number"]) < 1:
            raise ValueError("A posição deve ser um número inteiro maior que zero.")
        data["position_number"] = int(data["position_number"])
    else:
        data["position_number"] = None
    if not data["title"]:
        raise ValueError("Informe o título da proposta.")
    if data["priority"] not in {"critica", "alta", "normal", "baixa"}:
        raise ValueError("Prioridade inválida.")
    if data["source_link"]:
        parsed = urlparse(data["source_link"])
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("O link deve começar com http:// ou https:// e ser válido.")
    if any(len(str(value or "")) > 5000 for value in data.values()):
        raise ValueError("Um dos campos excede o limite permitido.")
    return data


def save_proposal(database_path, payload, proposal_id=None):
    initialize(database_path)
    data, now = validated_proposal(payload), now_iso()
    column_id = int(payload.get("column_id") or 0)
    with closing(connect(database_path)) as connection:
        with connection:
            column = connection.execute("SELECT name FROM kanban_columns WHERE id=?", (column_id,)).fetchone()
            if not column:
                raise ValueError("Selecione um portal válido.")
            data["portal"] = column["name"]
            values = [data[field] for field in FIELDS]
            try:
                if proposal_id:
                    previous = connection.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
                    if not previous:
                        raise FileNotFoundError("Proposta não encontrada.")
                    assignments = ",".join(f"{field}=?" for field in FIELDS)
                    connection.execute(f"UPDATE proposals SET column_id=?,{assignments},updated_at=? WHERE id=?", [column_id, *values, now, proposal_id])
                    if previous["column_id"] != column_id:
                        connection.execute(
                            "INSERT INTO proposal_stage_history(user_id,proposal_id,from_column_id,to_column_id,moved_at) VALUES('local',?,?,?,?)",
                            (proposal_id, previous["column_id"], column_id, now),
                        )
                else:
                    names = ",".join(FIELDS)
                    placeholders = ",".join("?" for _ in FIELDS)
                    cursor = connection.execute(
                        f"INSERT INTO proposals(user_id,column_id,{names},created_at,updated_at) VALUES('local',?,{placeholders},?,?)",
                        [column_id, *values, now, now],
                    )
                    proposal_id = cursor.lastrowid
            except sqlite3.IntegrityError as exc:
                raise ValueError("Já existe uma proposta igual neste portal.") from exc
            return row_dict(connection.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone())
    
    
def upsert_business_proposal(database_path, business_id, payload):
    """Keep exactly one classification card linked to a Block 4 business."""
    initialize(database_path)
    business_id = int(business_id)
    with closing(connect(database_path)) as connection:
        existing = connection.execute(
            "SELECT id FROM proposals WHERE user_id='local' AND business_id=?", (business_id,),
        ).fetchone()
    proposal = save_proposal(database_path, payload, existing["id"] if existing else None)
    with closing(connect(database_path)) as connection:
        with connection:
            connection.execute(
                "UPDATE proposals SET business_id=? WHERE id=?", (business_id, proposal["id"])
            )
            return row_dict(connection.execute(
                "SELECT * FROM proposals WHERE id=?", (proposal["id"],)
            ).fetchone())


def move_proposal(database_path, proposal_id, column_id):
    initialize(database_path)
    now = now_iso()

    with closing(connect(database_path)) as connection:
        with connection:
            proposal = connection.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
            column = connection.execute("SELECT * FROM kanban_columns WHERE id=?", (column_id,)).fetchone()
            if not proposal or not column:
                raise FileNotFoundError("Cartão ou coluna não encontrado.")
            if proposal["column_id"] == int(column_id):
                return row_dict(proposal)
            connection.execute("UPDATE proposals SET column_id=?,portal=?,updated_at=? WHERE id=?", (column_id, column["name"], now, proposal_id))
            connection.execute(
                "INSERT INTO proposal_stage_history(user_id,proposal_id,from_column_id,to_column_id,moved_at) VALUES('local',?,?,?,?)",
                (proposal_id, proposal["column_id"], column_id, now),
            )
            return row_dict(connection.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone())
    
    
def history(database_path, proposal_id):
    initialize(database_path)
    with closing(connect(database_path)) as connection:
        with connection:
            rows = connection.execute("""
                SELECT h.*,f.name AS from_column,t.name AS to_column
                FROM proposal_stage_history h LEFT JOIN kanban_columns f ON f.id=h.from_column_id
                JOIN kanban_columns t ON t.id=h.to_column_id
                WHERE h.proposal_id=? ORDER BY h.moved_at DESC,h.id DESC
            """, (proposal_id,)).fetchall()
        return [row_dict(row) for row in rows]
