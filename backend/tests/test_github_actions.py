from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

WORKFLOW_RELATIVE = Path(".github") / "workflows" / "backend.yml"


def _dayflow_repo_root() -> Path | None:
    workspace = os.environ.get("GITHUB_WORKSPACE")
    if workspace:
        return Path(workspace)
    for parent in Path(__file__).resolve().parents:
        if (parent / "backend").is_dir() and (
            (parent / "docker-compose.yml").is_file() or (parent / "frontend").is_dir()
        ):
            return parent
    return None


def _mapping_block(text: str, key: str) -> str:
    key_at_line = re.compile(rf"^(\s*){re.escape(key)}:\s*(.*)$")
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = key_at_line.match(line)
        if not match:
            continue
        indent, rest = match.group(1), match.group(2)
        if rest and rest not in {"|", ">", ">-", "|-"}:
            return rest
        collected: list[str] = []
        child_prefix = indent + " "
        for following in lines[index + 1 :]:
            if not following.strip() or following.lstrip().startswith("#"):
                collected.append(following)
                continue
            if following.startswith(child_prefix):
                collected.append(following)
                continue
            break
        return "\n".join(collected)
    return ""


def test_github_actions_runs_backend_pytest_on_push_and_pull_request():
    root = _dayflow_repo_root()
    if root is None:
        pytest.skip("Dayflow repo root is not mounted in this environment")

    workflow_path = root / WORKFLOW_RELATIVE
    assert workflow_path.is_file(), "expected .github/workflows/backend.yml"

    text = workflow_path.read_text(encoding="utf-8")

    on_block = _mapping_block(text, "on")
    assert re.search(r"\bpush\b", on_block)
    assert re.search(r"\bpull_request\b", on_block)

    assert "actions/checkout@" in text
    assert "actions/setup-python@" in text
    assert re.search(r"python-version:\s*['\"]?3\.12", text)
    assert re.search(r"pip install\s+-r\s+backend/requirements.txt", text)

    services_block = _mapping_block(text, "services")
    assert re.search(r"postgres:16", services_block)

    assert re.search(r"DATABASE_URL\s*[:=]", text)
    assert re.search(r"(?m)^\s+run:\s*.*\bpytest\b", text)
