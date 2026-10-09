"""LOAD_DATA: read and check tickets.json and kb_articles.json.

Broken input files fail here, at start-up, with a message naming the file and
the problem. Bad input is the operator's to fix, not something to guess around.
"""

import json
from pathlib import Path

from pydantic import BaseModel, ValidationError

from triage.schemas import Article, Ticket


class DataError(Exception):
    """An input file is missing, isn't valid JSON, or has a bad record."""


def load_tickets(path: str | Path) -> list[Ticket]:
    return _load_records(Path(path), Ticket, id_field="id", allow_empty=True)


def load_kb(path: str | Path) -> list[Article]:
    return _load_records(Path(path), Article, id_field="article_id", allow_empty=False)


def _load_records[M: BaseModel](
    path: Path, model: type[M], id_field: str, allow_empty: bool
) -> list[M]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise DataError(f"{path}: file not found") from None
    except json.JSONDecodeError as e:
        raise DataError(f"{path}: not valid JSON ({e.msg}, line {e.lineno} column {e.colno})") from None

    if not isinstance(raw, list):
        raise DataError(f"{path}: expected a JSON list of records, got {type(raw).__name__}")
    if not raw and not allow_empty:
        raise DataError(f"{path}: no records")

    records = []
    for i, item in enumerate(raw):
        try:
            records.append(model.model_validate(item))
        except ValidationError as e:
            raise DataError(f"{path}: record {i}: {_describe(e)}") from None

    seen: set[str] = set()
    for record in records:
        record_id = getattr(record, id_field)
        if record_id in seen:
            raise DataError(f"{path}: duplicate {id_field} {record_id!r}")
        seen.add(record_id)
    return records


def _describe(error: ValidationError) -> str:
    first = error.errors()[0]
    where = ".".join(str(part) for part in first["loc"]) or "record"
    more = f" (+{error.error_count() - 1} more)" if error.error_count() > 1 else ""
    return f"{where}: {first['msg']}{more}"
