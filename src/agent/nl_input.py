from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .config import Settings
from .tools import ToolRegistry


@dataclass
class ParsedReminderRequest:
    title: str
    scheduled_at: datetime
    end_at: datetime
    context: str | None
    source_text: str


@dataclass
class PendingConfirmation:
    title: str
    scheduled_at: datetime
    end_at: datetime
    context: str | None
    source_text: str


class NaturalLanguageInputService:
    def __init__(self, settings: Settings, tools: ToolRegistry) -> None:
        self.settings = settings
        self.tools = tools
        self._timezone = ZoneInfo(settings.timezone)
        self._pending_by_chat: dict[int, PendingConfirmation] = {}

    async def maybe_handle_message(self, chat_id: int, text: str) -> str | None:
        if not self.settings.natural_language_input_enabled:
            return None

        if chat_id in self._pending_by_chat:
            return await self._handle_confirmation(chat_id, text)

        if not self._looks_like_schedule_request(text):
            return None

        parsed = self._parse_request(text)
        if not parsed:
            return (
                "Boleh, tapi waktunya masih ambigu. Kasih format yang lebih jelas ya, "
                "misalnya `besok jam 15:00`, `besok jam 11-12`, atau `Senin jam 3 sore`."
            )

        self._pending_by_chat[chat_id] = PendingConfirmation(
            title=parsed.title,
            scheduled_at=parsed.scheduled_at,
            end_at=parsed.end_at,
            context=parsed.context,
            source_text=parsed.source_text,
        )
        return (
            f"Oke, aku set: {parsed.title} {self._format_confirmation_time(parsed.scheduled_at, parsed.end_at)}. "
            "Betul ya?"
        )

    async def _handle_confirmation(self, chat_id: int, text: str) -> str | None:
        pending = self._pending_by_chat[chat_id]
        lowered = text.lower().strip()

        if self._is_negative_reply(lowered):
            self._pending_by_chat.pop(chat_id, None)
            return "Oke, nggak jadi aku simpan. Kirim ulang aja dengan waktu yang lebih jelas kalau mau."

        if self._is_positive_reply(lowered):
            self._pending_by_chat.pop(chat_id, None)
            description = self._build_calendar_description(pending)
            result = await self.tools.calendar_create_event(
                summary=pending.title,
                start_iso=pending.scheduled_at.isoformat(),
                end_iso=pending.end_at.isoformat(),
                description=description,
            )
            if result.get("error"):
                return f"Gagal nyimpen ke Google Calendar: {result['error']}"
            return (
                f"Siap, udah aku simpan: {pending.title} {self._format_confirmation_time(pending.scheduled_at, pending.end_at)}."
            )

        reparsed = self._parse_request(text)
        if reparsed:
            self._pending_by_chat[chat_id] = PendingConfirmation(
                title=reparsed.title,
                scheduled_at=reparsed.scheduled_at,
                end_at=reparsed.end_at,
                context=reparsed.context,
                source_text=reparsed.source_text,
            )
            return (
                f"Oke, aku revisi: {reparsed.title} {self._format_confirmation_time(reparsed.scheduled_at, reparsed.end_at)}. "
                "Betul ya?"
            )

        return (
            f"Kalau mau lanjut, jawab `iya`. Kalau mau revisi, tulis ulang jadwalnya. "
            f"Sekarang yang pending: {pending.title} {self._format_confirmation_time(pending.scheduled_at, pending.end_at)}."
        )

    def _parse_request(self, text: str) -> ParsedReminderRequest | None:
        raw = text.strip()
        if not raw or not self._looks_like_schedule_request(raw):
            return None

        lowered = raw.lower()
        now = datetime.now(self._timezone)
        day_result = self._extract_day(lowered, now)
        if not day_result:
            return None

        scheduled_date, day_phrase, day_end = day_result
        time_result = self._extract_time_range(lowered)
        if not time_result:
            return None

        (
            start_hour,
            start_minute,
            end_hour,
            end_minute,
            time_phrase,
            time_start,
            time_end,
        ) = time_result
        scheduled_at = scheduled_date.replace(
            hour=start_hour,
            minute=start_minute,
            second=0,
            microsecond=0,
        )
        end_at = scheduled_date.replace(
            hour=end_hour,
            minute=end_minute,
            second=0,
            microsecond=0,
        )
        if end_at <= scheduled_at:
            end_at += timedelta(days=1)
        if scheduled_at <= now:
            if day_phrase in {"hari ini", "today"}:
                return None
            if day_phrase == "malam ini" and scheduled_at <= now:
                return None
        if end_at <= scheduled_at:
            return None

        title, context = self._extract_title_and_context(raw, lowered, day_end, time_start, time_end)
        if not title:
            return None

        return ParsedReminderRequest(
            title=title,
            scheduled_at=scheduled_at,
            end_at=end_at,
            context=context,
            source_text=raw,
        )

    @staticmethod
    def _looks_like_schedule_request(text: str) -> bool:
        lowered = text.lower()
        triggers = (
            "ingetin",
            "ingatkan",
            "remind",
            "jadwalin",
            "schedule",
            "pasang reminder",
            "buat reminder",
            "buat event",
            "bikin event",
            "tambahin ke kalender",
            "tambahin ke calendar",
            "masukin ke kalender",
            "masukin ke calendar",
            "masukkan ke kalender",
            "masukkan ke calendar",
            "calendar-in",
            "kalenderin",
        )
        return any(trigger in lowered for trigger in triggers)

    def _extract_day(self, text: str, now: datetime) -> tuple[datetime, str, int] | None:
        patterns = [
            ("lusa", 2),
            ("besok", 1),
            ("hari ini", 0),
            ("today", 0),
            ("malam ini", 0),
        ]
        for phrase, day_offset in patterns:
            match = re.search(rf"\b{re.escape(phrase)}\b", text)
            if match:
                base = now + timedelta(days=day_offset)
                return base, phrase, match.end()

        weekday_map = {
            "senin": 0,
            "selasa": 1,
            "rabu": 2,
            "kamis": 3,
            "jumat": 4,
            "jum'at": 4,
            "sabtu": 5,
            "minggu": 6,
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }
        for phrase, weekday in weekday_map.items():
            match = re.search(rf"\b{re.escape(phrase)}\b", text)
            if not match:
                continue
            days_ahead = (weekday - now.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            return now + timedelta(days=days_ahead), phrase, match.end()

        date_match = re.search(
            r"\b(?P<day>\d{1,2})(?:[/-](?P<month>\d{1,2})(?:[/-](?P<year>\d{2,4}))?| (?P<month_name>januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember))\b",
            text,
        )
        if not date_match:
            return None

        day = int(date_match.group("day"))
        month_name = date_match.group("month_name")
        if month_name:
            month_lookup = {
                "januari": 1,
                "februari": 2,
                "maret": 3,
                "april": 4,
                "mei": 5,
                "juni": 6,
                "juli": 7,
                "agustus": 8,
                "september": 9,
                "oktober": 10,
                "november": 11,
                "desember": 12,
            }
            month = month_lookup[month_name]
        else:
            month = int(date_match.group("month"))
        year_group = date_match.group("year")
        year = now.year
        if year_group:
            year = int(year_group)
            if year < 100:
                year += 2000
        try:
            scheduled = now.replace(year=year, month=month, day=day)
        except ValueError:
            return None
        if scheduled.date() < now.date() and not year_group:
            try:
                scheduled = scheduled.replace(year=year + 1)
            except ValueError:
                return None
        return scheduled, date_match.group(0), date_match.end()

    def _extract_time_range(
        self,
        text: str,
    ) -> tuple[int, int, int, int, str, int, int] | None:
        range_patterns = [
            (
                r"\b(?:(?:jam|pukul)\s*)?"
                r"(?P<start_hour>\d{1,2})(?:[:.](?P<start_minute>\d{2}))?"
                r"\s*(?P<start_period>pagi|siang|sore|malam)?"
                r"\s*(?:-|–|—|sampai|sampe|s/d|sd|to)\s*"
                r"(?P<end_hour>\d{1,2})(?:[:.](?P<end_minute>\d{2}))?"
                r"\s*(?P<end_period>pagi|siang|sore|malam)?\b"
            ),
        ]
        for pattern in range_patterns:
            match = re.search(pattern, text)
            if not match:
                continue

            start_period = match.group("start_period")
            end_period = match.group("end_period")
            inherited_start_period = start_period or end_period
            inherited_end_period = end_period or start_period

            start_time = self._normalize_time_component(
                int(match.group("start_hour")),
                int(match.group("start_minute") or "00"),
                inherited_start_period,
            )
            end_time = self._normalize_time_component(
                int(match.group("end_hour")),
                int(match.group("end_minute") or "00"),
                inherited_end_period,
            )
            if not start_time or not end_time:
                return None

            start_hour, start_minute = start_time
            end_hour, end_minute = end_time
            if (
                not start_period
                and not end_period
                and end_hour < start_hour
                and end_hour < 12
            ):
                end_hour += 12
            elif (
                not end_period
                and start_period in {"siang", "sore", "malam"}
                and end_hour < start_hour
                and end_hour < 12
            ):
                end_hour += 12

            return (
                start_hour,
                start_minute,
                end_hour,
                end_minute,
                match.group(0).strip(),
                match.start(),
                match.end(),
            )

        single_time = self._extract_single_time(text)
        if not single_time:
            return None

        start_hour, start_minute, time_phrase, time_start, time_end = single_time
        end_at = datetime(2000, 1, 1, start_hour, start_minute) + timedelta(
            minutes=self.settings.calendar_default_event_duration_minutes
        )
        return (
            start_hour,
            start_minute,
            end_at.hour,
            end_at.minute,
            time_phrase,
            time_start,
            time_end,
        )

    def _extract_single_time(self, text: str) -> tuple[int, int, str, int, int] | None:
        patterns = [
            r"\b(?:jam|pukul)\s*(?P<hour>\d{1,2})(?:[:.](?P<minute>\d{2}))?\s*(?P<period>pagi|siang|sore|malam)?\b",
            r"\b(?P<hour>\d{1,2})[:.](?P<minute>\d{2})\s*(?P<period>pagi|siang|sore|malam)?\b",
            r"\b(?P<hour>\d{1,2})\s*(?P<period>pagi|siang|sore|malam)\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if not match:
                continue
            normalized = self._normalize_time_component(
                int(match.group("hour")),
                int(match.group("minute") or "00"),
                match.group("period"),
            )
            if not normalized:
                return None
            hour, minute = normalized
            return hour, minute, match.group(0).strip(), match.start(), match.end()
        return None

    @staticmethod
    def _normalize_time_component(
        hour: int,
        minute: int,
        period: str | None,
    ) -> tuple[int, int] | None:
        if minute > 59 or hour > 23:
            return None
        if period:
            if hour < 1 or hour > 12:
                return None
            if period == "pagi":
                hour = 0 if hour == 12 else hour
            elif period == "siang":
                if 1 <= hour <= 10:
                    hour += 12
            elif period in {"sore", "malam"}:
                if 1 <= hour <= 11:
                    hour += 12
        return hour, minute

    def _extract_title_and_context(
        self,
        raw_text: str,
        lowered_text: str,
        day_end: int,
        time_start: int,
        time_end: int,
    ) -> tuple[str, str | None]:
        after_time = raw_text[time_end:].strip(" ,.-")
        after_time_lower = lowered_text[time_end:].strip(" ,.-")
        connector_match = re.search(r"\b(buat|untuk|to)\b", after_time_lower)
        if connector_match:
            content = after_time[connector_match.end():].strip(" ,.-")
        else:
            content = after_time

        content = re.sub(r"\b(ya|yah|dong|pls|please|tolong)\b$", "", content, flags=re.IGNORECASE).strip(" ,.-")
        if not content:
            content = raw_text
            content = re.sub(
                (
                    r"^(ingetin aku|ingatkan aku|remind me|jadwalin|schedule|buat reminder|"
                    r"buat event|bikin event|tambahin ke kalender|tambahin ke calendar|"
                    r"masukin ke kalender|masukin ke calendar|masukkan ke kalender|masukkan ke calendar)\s*"
                ),
                "",
                content,
                flags=re.IGNORECASE,
            )
            content = re.sub(
                r"\b(hari ini|besok|lusa|malam ini|senin|selasa|rabu|kamis|jumat|jum'at|sabtu|minggu|today)\b",
                "",
                content,
                flags=re.IGNORECASE,
            )
            content = re.sub(
                r"\b(?:jam|pukul)?\s*\d{1,2}(?:[:.]\d{2})?\s*(?:pagi|siang|sore|malam)?\s*(?:-|–|—|sampai|sampe|s/d|sd|to)\s*\d{1,2}(?:[:.]\d{2})?\s*(?:pagi|siang|sore|malam)?\b",
                "",
                content,
                flags=re.IGNORECASE,
            )
            content = re.sub(
                r"\b(?:jam|pukul)\s*\d{1,2}(?:[:.]\d{2})?\s*(?:pagi|siang|sore|malam)?\b",
                "",
                content,
                flags=re.IGNORECASE,
            )
            content = re.sub(
                r"\b\d{1,2}[:.]\d{2}\s*(?:pagi|siang|sore|malam)?\b",
                "",
                content,
                flags=re.IGNORECASE,
            )
            content = re.sub(
                r"\b\d{1,2}\s*(?:pagi|siang|sore|malam)\b",
                "",
                content,
                flags=re.IGNORECASE,
            )
            content = re.sub(r"^(buat|untuk|to)\s+", "", content.strip(), flags=re.IGNORECASE)
            content = content.strip(" ,.-")

        parts = [part.strip() for part in re.split(r"\s+-\s+|,\s*", content) if part.strip()]
        title = parts[0] if parts else ""
        context = ", ".join(parts[1:]) if len(parts) > 1 else None

        if not title:
            return "", None

        normalized_title = title[:1].upper() + title[1:]
        if context:
            context = context[:1].upper() + context[1:]
        return normalized_title, context

    @staticmethod
    def _is_positive_reply(text: str) -> bool:
        return text in {"iya", "iyaa", "ya", "y", "yes", "betul", "bener", "benar", "ok", "oke"}

    @staticmethod
    def _is_negative_reply(text: str) -> bool:
        return text in {"nggak", "ga", "gak", "tidak", "bukan", "jangan", "cancel", "batal"}

    def _format_confirmation_time(self, start_at: datetime, end_at: datetime) -> str:
        now = datetime.now(self._timezone).date()
        target_date = start_at.date()
        if target_date == now:
            day_label = "hari ini"
        elif target_date == now + timedelta(days=1):
            day_label = "besok"
        elif target_date == now + timedelta(days=2):
            day_label = "lusa"
        else:
            day_label = start_at.strftime("%A %d %b").lower()
        return f"{day_label} jam {start_at.strftime('%H:%M')}-{end_at.strftime('%H:%M')}"

    @staticmethod
    def _build_calendar_description(pending: PendingConfirmation) -> str:
        lines = [f"Source chat: {pending.source_text}"]
        if pending.context:
            lines.append(f"Konteks: {pending.context}")
        lines.append(
            "Waktu: "
            f"{pending.scheduled_at.strftime('%Y-%m-%d %H:%M')} - "
            f"{pending.end_at.strftime('%Y-%m-%d %H:%M')}"
        )
        lines.append(f"Target: {pending.title}")
        return "\n".join(lines)
