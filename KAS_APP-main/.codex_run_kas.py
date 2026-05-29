import re
import sqlite3
from pathlib import Path

import app as kas_app


BASE_DIR = Path(__file__).resolve().parent
LOCAL_DB = BASE_DIR / "database.db"


def _normalize_sql(query):
    query = query.replace("BIGSERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
    query = query.replace("DOUBLE PRECISION", "REAL")
    query = re.sub(r"\bTRUE\b", "1", query, flags=re.IGNORECASE)
    query = re.sub(r"\bFALSE\b", "0", query, flags=re.IGNORECASE)
    return query


class LocalConnection:
    def __init__(self):
        self.conn = sqlite3.connect(LOCAL_DB)
        self.conn.row_factory = self._dict_row_factory

    @staticmethod
    def _dict_row_factory(cursor, row):
        return {column[0]: row[index] for index, column in enumerate(cursor.description)}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, _exc, _tb):
        if exc_type:
            self.conn.rollback()
        else:
            self.conn.commit()
        self.conn.close()

    def _column_exists(self, table_name, column_name):
        rows = self.conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return any(row["name"] == column_name for row in rows)

    def _execute_alter_add_column(self, query):
        match = re.match(
            r"\s*ALTER\s+TABLE\s+(\w+)\s+ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+(\w+)\s+(.+)\s*",
            query,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return None

        table_name, column_name, column_definition = match.groups()
        if self._column_exists(table_name, column_name):
            return self.conn.execute(f"PRAGMA table_info({table_name})")

        column_definition = _normalize_sql(column_definition)
        column_definition = re.sub(r"\s+UNIQUE\b", "", column_definition, flags=re.IGNORECASE)
        return self.conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")

    def execute(self, query, params=None):
        alter_cursor = self._execute_alter_add_column(query)
        if alter_cursor is not None:
            return alter_cursor
        return self.conn.execute(_normalize_sql(query), tuple(params or ()))


def get_local_db_connection():
    return LocalConnection()


kas_app.get_db_connection = get_local_db_connection
app = kas_app.app
init_db = kas_app.init_db


if __name__ == "__main__":
    init_db()
    app.config["DATABASE_INITIALIZED"] = True
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
