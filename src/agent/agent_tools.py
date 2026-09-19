from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool

from obsidian_rag import search_vault
from obsidian_writer import append_to_daily_journal, create_note


class SearchObsidianInput(BaseModel):
    query: str = Field(description="Topik yang dicari di vault Obsidian")


class WriteObsidianInput(BaseModel):
    mode: Literal["new_note", "daily_journal"] = Field(
        description="new_note untuk file baru, daily_journal untuk entri jurnal harian"
    )
    content: str = Field(description="Isi catatan yang akan ditulis")
    title: str = Field(default="", description="Judul catatan untuk mode new_note")
    folder: str = Field(default="", description="Folder tujuan di vault Obsidian")


def search_obsidian_fn(query: str) -> str:
    results = search_vault(query)
    if not results:
        return "Tidak ditemukan catatan yang relevan di vault Obsidian."

    lines: list[str] = [f"Ditemukan {len(results)} catatan relevan:"]
    for result in results:
        excerpt = result["content"][:300].strip()
        lines.append(
            f"- {result['title']} ({result['filepath']}): {excerpt}{'...' if len(result['content']) > 300 else ''}"
        )
    return "\n".join(lines)


def write_obsidian_fn(
    mode: Literal["new_note", "daily_journal"],
    content: str,
    title: str = "",
    folder: str = "",
) -> str:
    if mode == "daily_journal":
        path = append_to_daily_journal(content)
        return f"Berhasil ditambahkan ke daily journal: `{path}`"

    note_title = title or "Untitled"
    path = create_note(note_title, content, folder)
    return f"Catatan baru dibuat: `{path}`"


search_obsidian_tool = StructuredTool.from_function(
    func=search_obsidian_fn,
    name="search_obsidian",
    description=(
        "Cari informasi dari vault Obsidian (second brain pribadi user). "
        "GUNAKAN untuk pertanyaan tentang catatan, ide, atau riset yang pernah ditulis user. "
        "JANGAN gunakan untuk informasi umum yang tidak personal."
    ),
    args_schema=SearchObsidianInput,
)

write_obsidian_tool = StructuredTool.from_function(
    func=write_obsidian_fn,
    name="write_obsidian_note",
    description=(
        "Buat catatan baru atau tambahkan entri ke daily journal di vault Obsidian. "
        "Gunakan saat user ingin menyimpan ide, draft, log harian, atau ringkasan pribadi."
    ),
    args_schema=WriteObsidianInput,
)

obsidian_tools = [search_obsidian_tool, write_obsidian_tool]
