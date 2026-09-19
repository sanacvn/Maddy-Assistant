from __future__ import annotations

import os

from langchain_google_genai import ChatGoogleGenerativeAI


def _create_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite",
        google_api_key=os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"),
        temperature=0.3,
        convert_system_message_to_human=True,
    )


class LazyGeminiLLM:
    def __init__(self) -> None:
        self._llm: ChatGoogleGenerativeAI | None = None

    def _get_llm(self) -> ChatGoogleGenerativeAI:
        if self._llm is None:
            self._llm = _create_llm()
        return self._llm

    def bind_tools(self, *args, **kwargs):
        return self._get_llm().bind_tools(*args, **kwargs)

    def __getattr__(self, attribute_name: str):
        return getattr(self._get_llm(), attribute_name)


llm = LazyGeminiLLM()

