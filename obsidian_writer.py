from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import frontmatter

from obsidian_rag import upsert_note_index


def _vault_path() -> Path:
    raw_path = os.getenv("OBSIDIAN_VAULT_PATH", "")
    if not raw_path:
        raise ValueError("OBSIDIAN_VAULT_PATH is not configured")
    return Path(raw_path).expanduser().resolve()


def _safe_folder(folder: str) -> Path:
    if not folder:
        return Path()
    return Path(folder)


def create_note(title: str, content: str, folder: str = "") -> str:
    vault_path = _vault_path()
    safe_title = title.replace("/", "-").replace(":", "-")
    target_dir = vault_path / _safe_folder(folder)
    target_dir.mkdir(parents=True, exist_ok=True)

    file_path = target_dir / f"{safe_title}.md"
    post = frontmatter.Post(
        content,
        title=title,
        created=datetime.now().isoformat(),
        tags=[],
    )

    file_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    upsert_note_index(file_path, vault_path=vault_path)
    return str(file_path.relative_to(vault_path))


def append_to_note(filepath_rel: str, text: str) -> bool:
    file_path = _vault_path() / Path(filepath_rel)
    if not file_path.exists():
        return False

    with file_path.open("a", encoding="utf-8") as file_handle:
        file_handle.write(f"\n{text}")
    upsert_note_index(file_path)
    return True


def append_to_daily_journal(text: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    journal_relative_path = Path("Journal") / f"{today}.md"
    journal_full_path = _vault_path() / journal_relative_path

    if not journal_full_path.exists():
        create_note(today, f"# {today}\n\n", folder="Journal")

    timestamp = datetime.now().strftime("%H:%M")
    append_to_note(str(journal_relative_path), f"- {timestamp} {text}")
    return str(journal_relative_path)
