import os
import re

from supabase import create_client


_TABLES = {"users", "analysis_sessions", "role_results"}


class DatabaseIntegrityError(Exception):
    pass


class DatabaseConfigurationError(Exception):
    pass


class SupabaseCursor:
    def __init__(self, connection):
        self.connection = connection
        self._rows = []
        self.lastrowid = None

    def execute(self, sql, params=()):
        statement = " ".join(sql.split())
        upper = statement.upper()
        params = list(params)

        try:
            if upper.startswith("SELECT "):
                self._select(statement, params)
            elif upper.startswith("INSERT INTO "):
                self._insert(statement, params)
            elif upper.startswith("UPDATE "):
                self._update(statement, params)
            else:
                raise ValueError(f"Unsupported database statement: {statement}")
        except Exception as exc:
            message = str(exc).lower()
            if "duplicate key" in message or "unique constraint" in message or "23505" in message:
                raise DatabaseIntegrityError(str(exc)) from exc
            raise

        return self

    def _select(self, statement, params):
        match = re.fullmatch(
            r"SELECT (.+?) FROM (\w+)(?: WHERE (.+?))?(?: ORDER BY (\w+) (ASC|DESC))?(?: LIMIT (\d+))?",
            statement,
            re.IGNORECASE,
        )
        if not match:
            raise ValueError(f"Unsupported SELECT statement: {statement}")

        columns, table, where, order_column, direction, limit = match.groups()
        self._check_table(table)
        query = self.connection.client.table(table).select(columns)

        param_index = 0
        if where:
            for condition in re.split(r"\s+AND\s+", where, flags=re.IGNORECASE):
                condition_match = re.fullmatch(r"(\w+)\s*=\s*\?", condition.strip())
                if not condition_match:
                    raise ValueError(f"Unsupported WHERE condition: {condition}")
                query = query.eq(condition_match.group(1), params[param_index])
                param_index += 1

        if order_column:
            query = query.order(order_column, desc=direction.upper() == "DESC")
        if limit:
            query = query.limit(int(limit))

        self._rows = query.execute().data or []
        self.lastrowid = None

    def _insert(self, statement, params):
        match = re.fullmatch(
            r"INSERT INTO (\w+) \((.+?)\) VALUES \((.+?)\)",
            statement,
            re.IGNORECASE,
        )
        if not match:
            raise ValueError(f"Unsupported INSERT statement: {statement}")

        table, column_text, placeholders = match.groups()
        self._check_table(table)
        columns = [column.strip() for column in column_text.split(",")]
        if len(columns) != len(params) or placeholders.count("?") != len(params):
            raise ValueError("Database insert parameter count does not match its columns")

        response = self.connection.client.table(table).insert(dict(zip(columns, params))).execute()
        self._rows = response.data or []
        self.lastrowid = self._rows[0].get("id") if self._rows else None

    def _update(self, statement, params):
        match = re.fullmatch(
            r"UPDATE (\w+) SET (\w+) = \? WHERE (\w+) = \?",
            statement,
            re.IGNORECASE,
        )
        if not match or len(params) != 2:
            raise ValueError(f"Unsupported UPDATE statement: {statement}")

        table, set_column, where_column = match.groups()
        self._check_table(table)
        response = (
            self.connection.client.table(table)
            .update({set_column: params[0]})
            .eq(where_column, params[1])
            .execute()
        )
        self._rows = response.data or []
        self.lastrowid = None

    @staticmethod
    def _check_table(table):
        if table not in _TABLES:
            raise ValueError(f"Unknown database table: {table}")

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class SupabaseConnection:
    def __init__(self):
        url = os.environ.get("SUPABASE_URL", "").strip()
        key = (
            os.environ.get("SUPABASE_SECRET_KEY", "").strip()
            or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
            or os.environ.get("SUPABASE_KEY", "").strip()
        )
        if not url or not key:
            raise DatabaseConfigurationError(
                "Set SUPABASE_URL and SUPABASE_SECRET_KEY in backend/.env"
            )
        if key.startswith("sb_publishable_"):
            raise DatabaseConfigurationError(
                "SUPABASE_KEY is publishable and cannot write protected tables. "
                "Paste the backend sb_secret key into SUPABASE_SECRET_KEY in backend/.env."
            )
        self.client = create_client(url, key)

    def cursor(self):
        return SupabaseCursor(self)

    def execute(self, sql, params=()):
        return self.cursor().execute(sql, params)

    def commit(self):
        pass

    def close(self):
        pass


def get_db_connection():
    return SupabaseConnection()


def verify_schema():
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = (
        os.environ.get("SUPABASE_SECRET_KEY", "").strip()
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.environ.get("SUPABASE_KEY", "").strip()
    )
    if not url or not key:
        raise DatabaseConfigurationError("Set the Supabase URL and API key in backend/.env")
    client = create_client(url, key)
    try:
        for table in sorted(_TABLES):
            client.table(table).select("id").limit(1).execute()
    except Exception as exc:
        raise RuntimeError(
            "Supabase tables are unavailable. Run backend/supabase_schema.sql in the Supabase SQL Editor."
        ) from exc
