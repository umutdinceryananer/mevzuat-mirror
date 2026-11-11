"""Turn data/*.json into one SQL file that rebuilds the D1 database.

The worker reads this database. Every run drops and recreates all tables
from worker/schema.sql, so the database always matches data/ exactly.
"""

import json
from pathlib import Path

from .normalize import normalize

# Dropped in this order, the search index first and documents last.
_TABLES = ["articles_fts", "articles", "documents"]


def build_sql(data_dir: Path, schema_file: Path) -> tuple[str, int, int]:
    """Return the SQL text, the number of documents and the number of articles."""
    statements = [f"DROP TABLE IF EXISTS {table};" for table in _TABLES]
    statements.append(schema_file.read_text(encoding="utf-8").strip())

    document_count = 0
    article_count = 0
    for path in sorted(data_dir.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        gazette = document.get("official_gazette") or {}
        statements.append(
            _insert(
                "documents",
                {
                    "id": document["id"],
                    "type": document["type"],
                    "number": document["number"],
                    "title": document["title"],
                    "short_names": document["short_names"],
                    "source_url": document["source_url"],
                    "accepted_at": document["accepted_at"],
                    "official_gazette_date": gazette.get("date"),
                    "official_gazette_number": gazette.get("number"),
                    "downloaded_at": document["downloaded_at"],
                    "latest_amendment_seen": document["latest_amendment_seen"],
                    "converter_version": document["converter_version"],
                    "article_count": len(document["articles"]),
                },
            )
        )
        document_count += 1

        for article in document["articles"]:
            statements.append(
                _insert(
                    "articles",
                    {
                        "document_id": document["id"],
                        "ord": article["order"],
                        "kind": article["kind"],
                        "number": article["number"],
                        "label": article["label"],
                        "heading": article["heading"],
                        "path": article["path"],
                        "repealed": article["repealed"],
                        "text": article["text"],
                        "notes": article["notes"],
                    },
                )
            )
            # The search index holds the normalized form, so that a query
            # typed without Turkish letters still finds the article.
            statements.append(
                _insert(
                    "articles_fts",
                    {
                        "document_id": document["id"],
                        "ord": article["order"],
                        "heading": normalize(article["heading"] or ""),
                        "text": normalize(article["text"]),
                    },
                )
            )
            article_count += 1

    return "\n".join(statements) + "\n", document_count, article_count


def _insert(table: str, row: dict) -> str:
    """Return one INSERT statement for a table and a row of values."""
    columns = ", ".join(row)
    values = ", ".join(_sql_literal(value) for value in row.values())
    return f"INSERT INTO {table} ({columns}) VALUES ({values});"


def _sql_literal(value: object) -> str:
    """Turn a Python value into an SQL literal.

    Lists become JSON text. Inside text, a single quote is written twice,
    which is how SQL escapes it.
    """
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (list, dict)):
        value = json.dumps(value, ensure_ascii=False)
    return "'" + str(value).replace("'", "''") + "'"
