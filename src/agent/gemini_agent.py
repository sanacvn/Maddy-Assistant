from __future__ import annotations
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from agent import agent_executor

from .config import Settings
from .tools import ToolRegistry


class GeminiTelegramAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.tools = ToolRegistry(settings)
        self.histories: dict[int, list[Any]] = {}

    async def respond(self, chat_id: int, user_text: str) -> str:
        history = self.histories.setdefault(chat_id, [])
        result = await agent_executor.ainvoke(
            {
                "input": user_text,
                "chat_history": history,
                "prefetched_context": "",
            }
        )
        reply_text = self._extract_reply(result)
        history.extend([HumanMessage(content=user_text), AIMessage(content=reply_text)])
        if len(history) > 20:
            del history[:-20]
        return reply_text

    def reset_history(self, chat_id: int) -> None:
        self.histories.pop(chat_id, None)

    @staticmethod
    def _extract_text(value: object) -> str | None:
        if isinstance(value, str):
            text = value.strip()
            return text or None
        if isinstance(value, dict):
            for key in ("text", "content", "output", "answer", "result"):
                extracted = GeminiTelegramAgent._extract_text(value.get(key))
                if extracted:
                    return extracted
            return None
        if isinstance(value, (list, tuple)):
            for item in value:
                extracted = GeminiTelegramAgent._extract_text(item)
                if extracted:
                    return extracted
        return None

    @staticmethod
    def _extract_reply(result: object) -> str:
        if isinstance(result, dict):
            extracted = GeminiTelegramAgent._extract_text(
                result.get("output")
                or result.get("text")
                or result.get("content")
                or result.get("output_text")
            )
            if extracted:
                return extracted
            return str(result)
        if isinstance(result, str):
            return result
        extracted = GeminiTelegramAgent._extract_text(result)
        if extracted:
            return extracted
        return str(result)
