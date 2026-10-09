import json

import pytest

from triage.data import DataError, load_kb, load_tickets


def write(tmp_path, content):
    path = tmp_path / "input.json"
    path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    return path


def test_sample_tickets_load():
    tickets = load_tickets("tickets.json")
    assert [t.id for t in tickets] == ["T1", "T2", "T3", "T4", "T5"]
    assert all(t.message and t.language == "en" for t in tickets)


def test_sample_kb_loads():
    kb = load_kb("kb_articles.json")
    assert [a.article_id for a in kb] == ["A1", "A2", "A3", "A4", "A5"]
    assert all(a.title and a.body for a in kb)


def test_missing_file(tmp_path):
    with pytest.raises(DataError, match="file not found"):
        load_tickets(tmp_path / "nope.json")


def test_invalid_json(tmp_path):
    with pytest.raises(DataError, match="not valid JSON"):
        load_tickets(write(tmp_path, '[{"id": "T1",'))


def test_not_a_list(tmp_path):
    with pytest.raises(DataError, match="expected a JSON list"):
        load_tickets(write(tmp_path, {"id": "T1", "message": "hi", "language": "en"}))


def test_missing_field_names_record_and_field(tmp_path):
    path = write(tmp_path, [{"id": "T1", "message": "hi", "language": "en"}, {"id": "T2", "language": "en"}])
    with pytest.raises(DataError, match=r"record 1: message"):
        load_tickets(path)


def test_wrong_type(tmp_path):
    with pytest.raises(DataError, match=r"record 0: id"):
        load_tickets(write(tmp_path, [{"id": 1, "message": "hi", "language": "en"}]))


def test_duplicate_ticket_ids(tmp_path):
    ticket = {"id": "T1", "message": "hi", "language": "en"}
    with pytest.raises(DataError, match="duplicate id 'T1'"):
        load_tickets(write(tmp_path, [ticket, ticket]))


def test_duplicate_article_ids(tmp_path):
    article = {"article_id": "A1", "title": "t", "body": "b"}
    with pytest.raises(DataError, match="duplicate article_id 'A1'"):
        load_kb(write(tmp_path, [article, article]))


def test_empty_kb_fails(tmp_path):
    with pytest.raises(DataError, match="no records"):
        load_kb(write(tmp_path, []))


def test_empty_ticket_list_is_allowed(tmp_path):
    assert load_tickets(write(tmp_path, [])) == []


def test_empty_message_is_allowed(tmp_path):
    [ticket] = load_tickets(write(tmp_path, [{"id": "T1", "message": "", "language": "en"}]))
    assert ticket.message == ""


def test_extra_input_fields_are_ignored(tmp_path):
    [ticket] = load_tickets(write(tmp_path, [{"id": "T1", "message": "hi", "language": "en", "channel": "email"}]))
    assert ticket.id == "T1"
