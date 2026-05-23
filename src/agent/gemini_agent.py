from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from .config import Settings
from .tools import ToolRegistry


logger = logging.getLogger(__name__)


class UpstreamServiceError(Exception):
    pass


class GeminiTelegramAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.tools = ToolRegistry(settings)
        self.histories: dict[int, list[dict[str, Any]]] = {}
        self.system_instruction = (
            "You are a practical AI assistant inside Telegram. "
            "Use tools whenever the user asks about Notion, calendar, time, or up-to-date web information. "
            "Before creating events or Notion pages, infer missing details from context when safe, otherwise ask a short follow-up. "
            "Respond in the user's language. "
            "Default tone: casual, confident, playful, and not stiff. "
            "Keep replies relatively short, use natural Indonesian slang when the user is casual, and avoid formal corporate phrasing. "
            "Match a 'bad bitch' energy lightly: sharp, witty, and expressive, but still helpful and readable. "
            "Do not be overly polite or do unnecessary small talk. "
            "Skip greetings, filler, and softening phrases unless the user explicitly wants them. "
            "Lead with the point, not pleasantries. "
            "If the topic is high-stakes, sensitive, or needs precision, keep the tone calmer and clearer."
        )

    async def respond(self, chat_id: int, user_text: str) -> str:
        history = self.histories.setdefault(chat_id, [])
        user_turn = {
            "role": "user",
            "parts": [{"text": user_text}],
        }
        history.append(user_turn)
        self._trim_history(history)

        for attempt in range(2):
            try:
                return await self._run_conversation(history)
            except UpstreamServiceError:
                return (
                    "Layanan Gemini sedang bermasalah sementara. "
                    "Coba kirim lagi dalam beberapa detik."
                )
            except httpx.HTTPStatusError as exc:
                if attempt == 0 and self._is_turn_sequence_error(exc):
                    logger.warning(
                        "Resetting corrupted chat history chat_id=%s after Gemini turn sequence error",
                        chat_id,
                    )
                    history[:] = [user_turn]
                    continue
                raise

        return "Saya tidak bisa menyelesaikan permintaan itu setelah beberapa langkah tool call."

    def reset_history(self, chat_id: int) -> None:
        self.histories.pop(chat_id, None)

    async def _run_conversation(self, history: list[dict[str, Any]]) -> str:
        for _ in range(6):
            response = await self._generate_content(history)
            candidate = response["candidates"][0]["content"]
            parts = candidate.get("parts", [])
            history.append(candidate)

            function_call = self._extract_function_call(parts)
            if function_call:
                tool_result = await self.tools.call(
                    function_call["name"],
                    function_call.get("args", {}),
                )
                history.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": function_call["name"],
                                    "response": tool_result,
                                }
                            }
                        ],
                    }
                )
                continue

            text = self._extract_text(parts)
            if text:
                return text

        return "Saya tidak bisa menyelesaikan permintaan itu setelah beberapa langkah tool call."

    async def _generate_content(self, history: list[dict[str, Any]]) -> dict[str, Any]:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.settings.gemini_model}:generateContent"
        )
        payload = {
            "systemInstruction": {
                "parts": [{"text": self.system_instruction}]
            },
            "contents": history,
            "tools": [
                {
                    "functionDeclarations": self.tools.get_function_declarations(),
                }
            ],
        }

        async with httpx.AsyncClient(timeout=60) as client:
            for attempt in range(3):
                try:
                    response = await client.post(
                        url,
                        params={"key": self.settings.gemini_api_key},
                        json=payload,
                    )
                    if response.status_code in {429, 500, 502, 503, 504}:
                        logger.warning(
                            "Gemini upstream temporary failure: status=%s body=%s",
                            response.status_code,
                            response.text[:500],
                        )
                        if attempt < 2:
                            await asyncio.sleep(1.5 * (attempt + 1))
                            continue
                        raise UpstreamServiceError(
                            f"Gemini temporary failure: HTTP {response.status_code}"
                        )

                    response.raise_for_status()
                    return response.json()
                except httpx.TimeoutException as exc:
                    logger.warning("Gemini request timed out on attempt %s", attempt + 1)
                    if attempt < 2:
                        await asyncio.sleep(1.5 * (attempt + 1))
                        continue
                    raise UpstreamServiceError("Gemini request timed out") from exc
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code
                    body = exc.response.text[:500]
                    logger.error("Gemini HTTP error: status=%s body=%s", status, body)
                    if status in {429, 500, 502, 503, 504} and attempt < 2:
                        await asyncio.sleep(1.5 * (attempt + 1))
                        continue
                    raise

        raise UpstreamServiceError("Gemini request failed after retries")

    @staticmethod
    def _extract_function_call(parts: list[dict[str, Any]]) -> dict[str, Any] | None:
        for part in parts:
            if "functionCall" in part:
                function_call = part["functionCall"]
                return {
                    "name": function_call["name"],
                    "args": function_call.get("args", {}),
                }
        return None

    @staticmethod
    def _extract_text(parts: list[dict[str, Any]]) -> str:
        chunks = [part.get("text", "") for part in parts if part.get("text")]
        return "\n".join(chunks).strip()

    @staticmethod
    def _is_turn_sequence_error(exc: httpx.HTTPStatusError) -> bool:
        if exc.response.status_code != 400:
            return False
        body = exc.response.text.lower()
        return "function call turn" in body or "function response turn" in body

    @staticmethod
    def _is_plain_user_turn(turn: dict[str, Any]) -> bool:
        if turn.get("role") != "user":
            return False
        for part in turn.get("parts", []):
            if part.get("text"):
                return True
        return False

    def _trim_history(self, history: list[dict[str, Any]], max_turns: int = 24) -> None:
        if len(history) <= max_turns:
            return

        trimmed = history[-max_turns:]
        while trimmed and not self._is_plain_user_turn(trimmed[0]):
            trimmed.pop(0)

        if trimmed:
            history[:] = trimmed
