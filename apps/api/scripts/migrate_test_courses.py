"""One-off: migrate db_session.add(Course(...)) to add_test_course() in tests."""

from __future__ import annotations

import re
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1] / "tests"
SKIP = {"test_workspaces.py"}  # intentional missing workspace_id test


def _ensure_import(text: str) -> str:
    if "add_test_course" in text:
        return text
    marker = "from tests.conftest import add_test_course\n"
    if marker in text:
        return text
    if "import pytest\n" in text:
        return text.replace("import pytest\n", f"import pytest\n\n{marker}", 1)
    return f"{marker}\n{text}"


def _convert_call(args: str) -> str | None:
    args = args.strip()
    if not args.startswith("id="):
        return None
    # Single-line Course(...) only
    if "\n" in args:
        return None
    m_id = re.match(r'id\s*=\s*("([^"]+)"|(\w+))', args)
    if not m_id:
        return None
    course_id = m_id.group(2) or m_id.group(3)
    rest = args[m_id.end() :].lstrip()
    if not rest.startswith(","):
        return None
    rest = rest[1:].lstrip()
    m_name = re.match(r'name\s*=\s*("([^"]+)"|(\w+))', rest)
    if not m_name:
        return None
    name = m_name.group(2) or m_name.group(3)
    kwargs = rest[m_name.end() :].strip()
    if kwargs.startswith(","):
        kwargs = kwargs[1:].strip()
    if kwargs.endswith(","):
        kwargs = kwargs[:-1].strip()
    if kwargs:
        return f'add_test_course(db_session, "{course_id}", "{name}", {kwargs})'
    return f'add_test_course(db_session, "{course_id}", "{name}")'


def migrate_file(path: Path) -> int:
    if path.name in SKIP:
        return 0
    text = path.read_text(encoding="utf-8")
    original = text
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        converted = _convert_call(match.group(1))
        if converted is None:
            return match.group(0)
        count += 1
        return converted

    text = re.sub(r"db_session\.add\(Course\(([^)]*)\)\)", repl, text)
    if count:
        text = _ensure_import(text)
        path.write_text(text, encoding="utf-8")
    return count


def main() -> None:
    total = 0
    for path in sorted(TESTS.glob("test_*.py")):
        n = migrate_file(path)
        if n:
            print(f"{path.name}: {n}")
            total += n
    print(f"Total conversions: {total}")


if __name__ == "__main__":
    main()
