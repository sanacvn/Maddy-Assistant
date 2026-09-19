from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import StructuredTool
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent

from llm_setup import llm
from langchain_tools import search_obsidian_tool, write_obsidian_tool
from src.agent.config import Settings
from src.agent.tools import ToolRegistry


def _load_system_prompt() -> str:
    system_prompt_path = Path(__file__).with_name("system.md")
    if system_prompt_path.exists():
        # `ChatPromptTemplate` treats single braces as template variables.
        # Escape them so the system prompt can contain literal braces safely.
        return (
            system_prompt_path.read_text(encoding="utf-8")
            .strip()
            .replace("{", "{{")
            .replace("}", "}}")
        )
    return (
        "Kamu adalah AI agent pribadi yang cerdas dan membantu.\n"
        "Kamu memiliki akses ke tools berikut dan harus menggunakannya sesuai konteks:\n\n"
        "- search_obsidian: untuk mencari catatan pribadi, ide, atau riset di vault Obsidian user\n"
        "- write_obsidian_note: untuk membuat catatan baru atau menambah entri ke daily journal\n"
        "- Google Calendar: untuk membuat event, cek jadwal, atau set reminder\n"
        "- Google Docs: untuk catatan jangka panjang\n\n"
        "ATURAN PENTING:\n"
        "1. Untuk pertanyaan tentang catatan atau jadwal PRIBADI user, SELALU gunakan tool — jangan menjawab dari asumsi.\n"
        "2. Jika query butuh lebih dari satu tool, gunakan secara berurutan.\n"
        "3. Jawab dalam Bahasa Indonesia kecuali user meminta bahasa lain.\n"
        "4. Setelah mendapat hasil dari tool, rangkum dengan bahasa yang natural dan ramah."
        "5. Jika mendapatkan kesamaan agenda dengan tool lainnya, print sekali saja"
    )


def _as_text(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2, default=str)


def _build_google_tools(settings: Settings) -> list[StructuredTool]:
    registry = ToolRegistry(settings)

    async def calendar_list_events_fn(start_iso: str, end_iso: str) -> str:
        return _as_text(await registry.calendar_list_events(start_iso, end_iso))

    async def calendar_create_event_fn(
        summary: str,
        start_iso: str,
        end_iso: str,
        description: str = "",
    ) -> str:
        return _as_text(
            await registry.calendar_create_event(
                summary=summary,
                start_iso=start_iso,
                end_iso=end_iso,
                description=description,
            )
        )

    async def calendar_check_setup_fn() -> str:
        return _as_text(await registry.calendar_check_setup())

    async def google_docs_read_fn(
        document_id: str | None = None,
        max_chars: int = 6000,
    ) -> str:
        return _as_text(
            await registry.google_docs_read(
                document_id=document_id,
                max_chars=max_chars,
            )
        )

    async def google_docs_append_fn(text: str, document_id: str | None = None) -> str:
        return _as_text(
            await registry.google_docs_append(text=text, document_id=document_id)
        )

    async def google_docs_replace_fn(text: str, document_id: str | None = None) -> str:
        return _as_text(
            await registry.google_docs_replace(text=text, document_id=document_id)
        )

    async def google_docs_check_setup_fn(document_id: str | None = None) -> str:
        return _as_text(
            await registry.google_docs_check_setup(document_id=document_id)
        )

    return [
        StructuredTool.from_function(
            coroutine=calendar_list_events_fn,
            name="calendar_list_events",
            description="List event Google Calendar dalam rentang waktu tertentu.",
        ),
        StructuredTool.from_function(
            coroutine=calendar_create_event_fn,
            name="calendar_create_event",
            description="Buat event Google Calendar baru.",
        ),
        StructuredTool.from_function(
            coroutine=calendar_check_setup_fn,
            name="calendar_check_setup",
            description="Cek konfigurasi dan akses Google Calendar.",
        ),
        StructuredTool.from_function(
            coroutine=google_docs_read_fn,
            name="google_docs_read",
            description="Baca isi Google Docs yang dipakai sebagai konteks atau dokumen kolaboratif.",
        ),
        StructuredTool.from_function(
            coroutine=google_docs_append_fn,
            name="google_docs_append",
            description="Tambahkan teks ke akhir Google Docs.",
        ),
        StructuredTool.from_function(
            coroutine=google_docs_replace_fn,
            name="google_docs_replace",
            description="Ganti isi utama Google Docs.",
        ),
        StructuredTool.from_function(
            coroutine=google_docs_check_setup_fn,
            name="google_docs_check_setup",
            description="Cek konfigurasi dan akses Google Docs.",
        ),
    ]


def build_all_tools(settings: Settings | None = None) -> list[StructuredTool]:
    active_settings = settings or Settings.from_env()
    all_tools: list[StructuredTool] = [
        search_obsidian_tool,
        write_obsidian_tool,
        *_build_google_tools(active_settings),
    ]
    return all_tools


def build_agent_executor(settings: Settings | None = None) -> AgentExecutor:
    active_settings = settings or Settings.from_env()
    all_tools = build_all_tools(active_settings)
    system_prompt = _load_system_prompt()
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("system", "Live context:\n{prefetched_context}"),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )
    agent = create_tool_calling_agent(llm, all_tools, prompt)
    return AgentExecutor(
        agent=agent,
        tools=all_tools,
        max_iterations=6,
        handle_parsing_errors=True,
        early_stopping_method="generate",
        verbose=False,
    )


class LazyAgentExecutor:
    def __init__(self) -> None:
        self._executor: AgentExecutor | None = None

    def _get_executor(self) -> AgentExecutor:
        if self._executor is None:
            self._executor = build_agent_executor()
        return self._executor

    async def ainvoke(self, inputs: dict[str, Any], config: dict[str, Any] | None = None):
        executor = self._get_executor()
        if config is None:
            return await executor.ainvoke(inputs)
        return await executor.ainvoke(inputs, config=config)

    def invoke(self, inputs: dict[str, Any], config: dict[str, Any] | None = None):
        executor = self._get_executor()
        if config is None:
            return executor.invoke(inputs)
        return executor.invoke(inputs, config=config)

    def __getattr__(self, attribute_name: str):
        return getattr(self._get_executor(), attribute_name)


agent_executor = LazyAgentExecutor()
