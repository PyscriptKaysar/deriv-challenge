import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
FILES = ["main.py", "validate.py", "tickets.json", "kb_articles.json", "README.md"]


@pytest.fixture
def project(tmp_path):
    for name in FILES:
        shutil.copy(ROOT / name, tmp_path / name)
    shutil.copytree(ROOT / "triage", tmp_path / "triage", ignore=shutil.ignore_patterns("__pycache__"))
    subprocess.run([sys.executable, "main.py"], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path


def validate(path):
    return subprocess.run([sys.executable, "validate.py"], cwd=path, capture_output=True, text=True)


def test_passes_on_real_output(project):
    run = validate(project)
    assert run.returncode == 0, run.stdout


def test_fails_when_t4_result_is_missing(project):
    results = json.loads((project / "results.json").read_text(encoding="utf-8"))
    (project / "results.json").write_text(json.dumps([r for r in results if r["ticket_id"] != "T4"]), encoding="utf-8")
    run = validate(project)
    assert run.returncode == 1
    assert "FAIL  T4 is safely refused" in run.stdout


def test_fails_when_t4_is_answered_instead_of_refused(project):
    results = json.loads((project / "results.json").read_text(encoding="utf-8"))
    for r in results:
        if r["ticket_id"] == "T4":
            r["reply_draft"] = "Gold looks strong today."
    (project / "results.json").write_text(json.dumps(results), encoding="utf-8")
    assert validate(project).returncode == 1


def test_fails_on_unknown_article_id(project):
    results = json.loads((project / "results.json").read_text(encoding="utf-8"))
    results[0]["retrieved_articles"] = ["A99"]
    (project / "results.json").write_text(json.dumps(results), encoding="utf-8")
    run = validate(project)
    assert run.returncode == 1
    assert "FAIL  retrieved article IDs are valid" in run.stdout
