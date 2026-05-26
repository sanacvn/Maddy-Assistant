from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from playwright.async_api import async_playwright

from .config import Settings


logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._local_task_lock = asyncio.Lock()
        self._timezone = ZoneInfo(settings.timezone)

    def get_function_declarations(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "notion_search",
                "description": "Search pages in Notion by a text query.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {"type": "STRING", "description": "Search query for Notion content."}
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "notion_create_page",
                "description": "Create a Notion page under a parent page with plain text content.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "title": {"type": "STRING"},
                        "content": {"type": "STRING"},
                        "parent_page_id": {
                            "type": "STRING",
                            "description": "Optional Notion parent page ID. Defaults to NOTION_PARENT_PAGE_ID."
                        },
                    },
                    "required": ["title", "content"],
                },
            },
            {
                "name": "calendar_list_events",
                "description": "List events from Google Calendar in a time range.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "start_iso": {"type": "STRING", "description": "RFC3339 ISO datetime."},
                        "end_iso": {"type": "STRING", "description": "RFC3339 ISO datetime."},
                    },
                    "required": ["start_iso", "end_iso"],
                },
            },
            {
                "name": "calendar_create_event",
                "description": "Create a Google Calendar event.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "summary": {"type": "STRING"},
                        "start_iso": {"type": "STRING", "description": "RFC3339 ISO datetime."},
                        "end_iso": {"type": "STRING", "description": "RFC3339 ISO datetime."},
                        "description": {"type": "STRING"},
                    },
                    "required": ["summary", "start_iso", "end_iso"],
                },
            },
            {
                "name": "calendar_check_setup",
                "description": "Check Google Calendar configuration and permissions.",
                "parameters": {"type": "OBJECT", "properties": {}},
            },
            {
                "name": "google_docs_read",
                "description": "Read plain text content from a Google Docs document used as persistent context.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "document_id": {
                            "type": "STRING",
                            "description": "Optional Google Docs document ID or full URL. Defaults to GOOGLE_DOCS_DOCUMENT_ID.",
                        },
                        "max_chars": {
                            "type": "INTEGER",
                            "description": "Maximum characters to return from the document content.",
                        },
                    },
                },
            },
            {
                "name": "google_docs_append",
                "description": "Append plain text to the end of a Google Docs document used as persistent context.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "text": {"type": "STRING"},
                        "document_id": {
                            "type": "STRING",
                            "description": "Optional Google Docs document ID or full URL. Defaults to GOOGLE_DOCS_DOCUMENT_ID.",
                        },
                    },
                    "required": ["text"],
                },
            },
            {
                "name": "google_docs_replace",
                "description": "Replace the main body content of a Google Docs document with new plain text.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "text": {"type": "STRING"},
                        "document_id": {
                            "type": "STRING",
                            "description": "Optional Google Docs document ID or full URL. Defaults to GOOGLE_DOCS_DOCUMENT_ID.",
                        },
                    },
                    "required": ["text"],
                },
            },
            {
                "name": "google_docs_check_setup",
                "description": "Check Google Docs configuration and whether the configured document is accessible to the bot.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "document_id": {
                            "type": "STRING",
                            "description": "Optional Google Docs document ID or full URL. Defaults to GOOGLE_DOCS_DOCUMENT_ID.",
                        }
                    },
                },
            },
            {
                "name": "web_search",
                "description": "Search the web for current information.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {"type": "STRING"},
                        "max_results": {"type": "INTEGER"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "browser_fetch",
                "description": "Open a web page and extract readable text from it.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "url": {"type": "STRING"},
                    },
                    "required": ["url"],
                },
            },
            {
                "name": "get_current_time",
                "description": "Get current time in the configured timezone.",
                "parameters": {"type": "OBJECT", "properties": {}},
            },
        ]

    async def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        handlers = {
            "notion_search": self.notion_search,
            "notion_create_page": self.notion_create_page,
            "calendar_list_events": self.calendar_list_events,
            "calendar_create_event": self.calendar_create_event,
            "calendar_check_setup": self.calendar_check_setup,
            "google_docs_read": self.google_docs_read,
            "google_docs_append": self.google_docs_append,
            "google_docs_replace": self.google_docs_replace,
            "google_docs_check_setup": self.google_docs_check_setup,
            "web_search": self.web_search,
            "browser_fetch": self.browser_fetch,
            "get_current_time": self.get_current_time,
        }
        if name not in handlers:
            return {"error": f"Unknown tool: {name}"}

        try:
            return await handlers[name](**args)
        except Exception as exc:
            return {"error": str(exc), "tool": name}

    async def list_urgent_tasks(
        self,
        now: datetime,
        window_hours: int = 3,
        deadline_before: datetime | None = None,
    ) -> list[dict[str, Any]]:
        await self.ensure_daily_tasks(now)
        providers = self._enabled_task_providers()
        deadline_before = deadline_before or (now + timedelta(hours=window_hours))
        tasks: list[dict[str, Any]] = []

        for provider in providers:
            try:
                if provider == "local":
                    tasks.extend(await self._local_list_urgent_tasks(now, deadline_before))
                elif provider == "notion":
                    tasks.extend(await self._notion_list_urgent_tasks(now, deadline_before))
                elif provider == "todoist":
                    tasks.extend(await self._todoist_list_urgent_tasks(now, deadline_before))
                elif provider == "google_tasks":
                    tasks.extend(await self._google_tasks_list_urgent_tasks(now, deadline_before))
            except Exception:
                logger.exception("Urgent task provider failed provider=%s", provider)
                continue

        return tasks

    async def ensure_daily_tasks(self, now: datetime | None = None) -> list[dict[str, Any]]:
        if not self.settings.daily_task_list_enabled or not self.settings.daily_task_templates:
            return []

        current = now.astimezone(self._timezone) if now else datetime.now(self._timezone)
        due_at = current.replace(
            hour=self.settings.daily_task_due_hour,
            minute=self.settings.daily_task_due_minute,
            second=0,
            microsecond=0,
        )
        created: list[dict[str, Any]] = []

        async with self._local_task_lock:
            items = self._load_local_tasks_unlocked()
            pruned_items = self._prune_local_tasks(items, current)
            changed = len(pruned_items) != len(items)
            items = pruned_items
            existing_keys = {
                identity
                for identity in (self._local_task_identity(item) for item in items)
                if identity
            }

            for title in self.settings.daily_task_templates:
                daily_key = self._daily_task_key(current, title)
                if daily_key in existing_keys:
                    continue

                item = {
                    "id": daily_key,
                    "title": title,
                    "due": due_at.isoformat(),
                    "status": "needsAction",
                    "notes": "Auto-generated daily task.",
                    "daily_key": daily_key,
                    "created_at": current.isoformat(),
                }
                items.append(item)
                existing_keys.add(daily_key)
                changed = True
                created.append(
                    {
                        "task_key": f"local:{daily_key}",
                        "source": "local",
                        "task_id": daily_key,
                        "task_name": title,
                        "deadline_at": due_at,
                        "progress": item["notes"],
                        "status": item["status"],
                        "url": None,
                    }
                )

            if changed:
                self._save_local_tasks_unlocked(items)

        return created

    async def notion_search(self, query: str) -> dict[str, Any]:
        if not self.settings.notion_api_key:
            return {"error": "NOTION_API_KEY is not configured."}

        headers = self._notion_headers()
        payload = {"query": query, "page_size": 5}

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.notion.com/v1/search",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data.get("results", []):
            title = self._extract_notion_title(item)
            results.append(
                {
                    "id": item.get("id"),
                    "url": item.get("url"),
                    "object": item.get("object"),
                    "title": title,
                }
            )
        return {"results": results}

    async def notion_extract_task_context(self, task_name: str) -> dict[str, Any]:
        search_result = await self.notion_search(task_name)
        if search_result.get("error"):
            return {}

        results = search_result.get("results", [])
        if not results:
            return {}

        page = self._pick_best_notion_result(task_name, results)
        page_id = page.get("id")
        if not page_id:
            return {}

        lines = await self._notion_page_lines(page_id)
        context, target = self._extract_context_and_target(lines)
        return {
            "page_id": page_id,
            "page_title": page.get("title"),
            "page_url": page.get("url"),
            "context": context,
            "target": target,
        }

    async def notion_create_page(
        self,
        title: str,
        content: str,
        parent_page_id: str | None = None,
    ) -> dict[str, Any]:
        if not self.settings.notion_api_key:
            return {"error": "NOTION_API_KEY is not configured."}

        parent_id = parent_page_id or self.settings.notion_parent_page_id
        if not parent_id:
            return {"error": "Missing parent_page_id and NOTION_PARENT_PAGE_ID is not configured."}

        headers = self._notion_headers()
        payload = {
            "parent": {"type": "page_id", "page_id": parent_id},
            "properties": {
                "title": {
                    "title": [
                        {
                            "type": "text",
                            "text": {"content": title},
                        }
                    ]
                }
            },
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {"content": content[:1800]},
                            }
                        ]
                    },
                }
            ],
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.notion.com/v1/pages",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        return {"id": data.get("id"), "url": data.get("url"), "title": title}

    async def calendar_list_events(self, start_iso: str, end_iso: str) -> dict[str, Any]:
        service = self._calendar_service()
        try:
            result = (
                service.events()
                .list(
                    calendarId=self.settings.google_calendar_id,
                    timeMin=start_iso,
                    timeMax=end_iso,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=10,
                )
                .execute()
            )
        except HttpError as exc:
            return self._calendar_http_error(exc)
        events = [
            {
                "id": item.get("id"),
                "summary": item.get("summary"),
                "description": item.get("description", ""),
                "start": item.get("start", {}).get("dateTime") or item.get("start", {}).get("date"),
                "end": item.get("end", {}).get("dateTime") or item.get("end", {}).get("date"),
                "htmlLink": item.get("htmlLink"),
            }
            for item in result.get("items", [])
        ]
        return {"events": events}

    async def calendar_create_event(
        self,
        summary: str,
        start_iso: str,
        end_iso: str,
        description: str = "",
    ) -> dict[str, Any]:
        service = self._calendar_service()
        start_value = self._calendar_event_datetime_value(start_iso)
        end_value = self._calendar_event_datetime_value(end_iso)
        event = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start_value},
            "end": {"dateTime": end_value},
        }
        try:
            created = service.events().insert(
                calendarId=self.settings.google_calendar_id,
                body=event,
            ).execute()
        except HttpError as exc:
            return self._calendar_http_error(exc)
        return {
            "id": created.get("id"),
            "htmlLink": created.get("htmlLink"),
            "summary": created.get("summary"),
        }

    async def calendar_check_setup(self) -> dict[str, Any]:
        service_account_file = self.settings.google_service_account_file
        if not service_account_file:
            return {"ok": False, "error": "GOOGLE_SERVICE_ACCOUNT_FILE is not configured."}

        file_path = Path(service_account_file)
        if not file_path.exists():
            return {"ok": False, "error": f"Service account file not found: {service_account_file}"}

        try:
            credentials = service_account.Credentials.from_service_account_file(
                service_account_file,
                scopes=["https://www.googleapis.com/auth/calendar"],
            )
        except Exception as exc:
            return {"ok": False, "error": f"Failed to load service account file: {exc}"}

        service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        try:
            calendar = service.calendars().get(calendarId=self.settings.google_calendar_id).execute()
        except HttpError as exc:
            result = self._calendar_http_error(exc)
            result["service_account_email"] = credentials.service_account_email
            result["calendar_id"] = self.settings.google_calendar_id
            return result

        return {
            "ok": True,
            "calendar_id": self.settings.google_calendar_id,
            "calendar_summary": calendar.get("summary"),
            "calendar_time_zone": calendar.get("timeZone"),
            "service_account_email": credentials.service_account_email,
            "note": (
                "If this is not the expected calendar, set GOOGLE_CALENDAR_ID to the exact "
                "calendar ID or Gmail address of the shared calendar."
            ),
        }

    async def google_docs_read(
        self,
        document_id: str | None = None,
        max_chars: int = 12000,
    ) -> dict[str, Any]:
        try:
            resolved_document_id = self._google_docs_resolve_document_id(document_id)
            document = self._google_docs_load_document(
                resolved_document_id,
                readonly=True,
            )
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        except HttpError as exc:
            result = self._google_docs_http_error(exc)
            result["document_id"] = self._google_docs_extract_document_id(
                document_id or self.settings.google_docs_document_id
            )
            return result

        content = self._google_docs_plain_text(document)
        safe_limit = min(20000, max(500, max_chars))
        return {
            "ok": True,
            "document_id": resolved_document_id,
            "title": document.get("title") or "Untitled",
            "document_url": self._google_docs_url(resolved_document_id),
            "content": content[:safe_limit],
            "truncated": len(content) > safe_limit,
            "word_count": len(content.split()),
        }

    async def google_docs_append(
        self,
        text: str,
        document_id: str | None = None,
    ) -> dict[str, Any]:
        clean_text = text.strip()
        if not clean_text:
            return {"ok": False, "error": "text cannot be empty."}

        try:
            resolved_document_id = self._google_docs_resolve_document_id(document_id)
            document = self._google_docs_load_document(resolved_document_id, readonly=False)
            existing_content = self._google_docs_plain_text(document)
            insert_index = self._google_docs_end_index(document)
            prefix = "\n\n" if existing_content.strip() else ""
            body = {
                "requests": [
                    {
                        "insertText": {
                            "location": {"index": insert_index},
                            "text": f"{prefix}{clean_text}",
                        }
                    }
                ]
            }
            self._google_docs_service(readonly=False).documents().batchUpdate(
                documentId=resolved_document_id,
                body=body,
            ).execute()
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        except HttpError as exc:
            result = self._google_docs_http_error(exc)
            result["document_id"] = self._google_docs_extract_document_id(
                document_id or self.settings.google_docs_document_id
            )
            return result

        updated_document = self._google_docs_load_document(resolved_document_id, readonly=True)
        updated_content = self._google_docs_plain_text(updated_document)
        return {
            "ok": True,
            "document_id": resolved_document_id,
            "title": updated_document.get("title") or "Untitled",
            "document_url": self._google_docs_url(resolved_document_id),
            "appended_chars": len(clean_text),
            "word_count": len(updated_content.split()),
        }

    async def google_docs_replace(
        self,
        text: str,
        document_id: str | None = None,
    ) -> dict[str, Any]:
        clean_text = text.strip()
        if not clean_text:
            return {"ok": False, "error": "text cannot be empty."}

        try:
            resolved_document_id = self._google_docs_resolve_document_id(document_id)
            document = self._google_docs_load_document(resolved_document_id, readonly=False)
            requests: list[dict[str, Any]] = []
            body_end_index = self._google_docs_body_end_index(document)
            if body_end_index > 1:
                requests.append(
                    {
                        "deleteContentRange": {
                            "range": {
                                "startIndex": 1,
                                "endIndex": body_end_index,
                            }
                        }
                    }
                )
            requests.append(
                {
                    "insertText": {
                        "location": {"index": 1},
                        "text": clean_text,
                    }
                }
            )
            self._google_docs_service(readonly=False).documents().batchUpdate(
                documentId=resolved_document_id,
                body={"requests": requests},
            ).execute()
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        except HttpError as exc:
            result = self._google_docs_http_error(exc)
            result["document_id"] = self._google_docs_extract_document_id(
                document_id or self.settings.google_docs_document_id
            )
            return result

        updated_document = self._google_docs_load_document(resolved_document_id, readonly=True)
        updated_content = self._google_docs_plain_text(updated_document)
        return {
            "ok": True,
            "document_id": resolved_document_id,
            "title": updated_document.get("title") or "Untitled",
            "document_url": self._google_docs_url(resolved_document_id),
            "word_count": len(updated_content.split()),
        }

    async def google_docs_check_setup(self, document_id: str | None = None) -> dict[str, Any]:
        service_account_file = self.settings.google_service_account_file
        if not service_account_file:
            return {"ok": False, "error": "GOOGLE_SERVICE_ACCOUNT_FILE is not configured."}

        file_path = Path(service_account_file)
        if not file_path.exists():
            return {"ok": False, "error": f"Service account file not found: {service_account_file}"}

        try:
            resolved_document_id = self._google_docs_resolve_document_id(document_id)
            credentials = service_account.Credentials.from_service_account_file(
                service_account_file,
                scopes=["https://www.googleapis.com/auth/documents"],
            )
            document = build(
                "docs",
                "v1",
                credentials=credentials,
                cache_discovery=False,
            ).documents().get(documentId=resolved_document_id).execute()
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        except HttpError as exc:
            result = self._google_docs_http_error(exc)
            result["document_id"] = self._google_docs_extract_document_id(
                document_id or self.settings.google_docs_document_id
            )
            return result
        except Exception as exc:
            return {"ok": False, "error": f"Failed to load Google Docs setup: {exc}"}

        content = self._google_docs_plain_text(document)
        return {
            "ok": True,
            "document_id": resolved_document_id,
            "title": document.get("title") or "Untitled",
            "document_url": self._google_docs_url(resolved_document_id),
            "service_account_email": credentials.service_account_email,
            "word_count": len(content.split()),
            "note": (
                "Share the document directly to this service account email with Editor access "
                "if you want the bot to append or replace content."
            ),
        }

    async def web_search(self, query: str, max_results: int = 5) -> dict[str, Any]:
        params = {"q": query}
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get("https://duckduckgo.com/html/", params=params)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        for result in soup.select(".result")[:max_results]:
            anchor = result.select_one(".result__title a")
            snippet = result.select_one(".result__snippet")
            if not anchor:
                continue
            results.append(
                {
                    "title": anchor.get_text(" ", strip=True),
                    "url": anchor.get("href"),
                    "snippet": snippet.get_text(" ", strip=True) if snippet else "",
                }
            )
        return {"results": results}

    async def browser_fetch(self, url: str) -> dict[str, Any]:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=self.settings.playwright_headless)
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(1500)
            title = await page.title()
            body_text = await page.locator("body").inner_text()
            await browser.close()
        cleaned = " ".join(body_text.split())
        return {
            "title": title,
            "url": url,
            "content": cleaned[:4000],
        }

    async def get_current_time(self) -> dict[str, Any]:
        now = datetime.now(ZoneInfo(self.settings.timezone))
        return {
            "iso": now.isoformat(),
            "timezone": self.settings.timezone,
        }

    def _calendar_service(self):
        if not self.settings.google_service_account_file:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_FILE is not configured.")

        credentials = service_account.Credentials.from_service_account_file(
            self.settings.google_service_account_file,
            scopes=["https://www.googleapis.com/auth/calendar"],
        )
        return build("calendar", "v3", credentials=credentials, cache_discovery=False)

    def _calendar_http_error(self, exc: HttpError) -> dict[str, Any]:
        status = getattr(exc.resp, "status", None)
        content = ""
        if getattr(exc, "content", None):
            try:
                content = exc.content.decode("utf-8", errors="ignore")[:500]
            except Exception:
                content = str(exc)[:500]

        if status == 404:
            return {
                "ok": False,
                "error": (
                    "Google Calendar tidak ditemukan. Jika memakai service account, jangan pakai "
                    "GOOGLE_CALENDAR_ID=primary. Isi GOOGLE_CALENDAR_ID dengan ID kalender yang benar "
                    "atau email Gmail kalender target, lalu share kalender itu ke email service account."
                ),
                "status": status,
                "details": content,
            }
        if status == 403:
            return {
                "ok": False,
                "error": (
                    "Akses Google Calendar ditolak. Pastikan Calendar API aktif dan kalender target "
                    "sudah di-share ke email service account dengan izin yang cukup."
                ),
                "status": status,
                "details": content,
            }

        return {
            "ok": False,
            "error": f"Google Calendar API error: HTTP {status}",
            "status": status,
            "details": content or str(exc),
        }

    def _calendar_event_datetime_value(self, value: str) -> str:
        parsed = self._parse_datetime(value)
        if not parsed:
            return value
        return parsed.astimezone(ZoneInfo(self.settings.timezone)).isoformat()

    def _google_docs_service(self, readonly: bool):
        if not self.settings.google_service_account_file:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_FILE is not configured.")

        scope = (
            "https://www.googleapis.com/auth/documents.readonly"
            if readonly
            else "https://www.googleapis.com/auth/documents"
        )
        credentials = service_account.Credentials.from_service_account_file(
            self.settings.google_service_account_file,
            scopes=[scope],
        )
        return build("docs", "v1", credentials=credentials, cache_discovery=False)

    def _google_docs_resolve_document_id(self, document_id: str | None) -> str:
        raw_value = document_id or self.settings.google_docs_document_id
        if not raw_value:
            raise ValueError(
                "Missing Google Docs document ID. Set GOOGLE_DOCS_DOCUMENT_ID or pass document_id."
            )

        resolved = self._google_docs_extract_document_id(raw_value)
        if not resolved:
            raise ValueError(
                "Invalid Google Docs document ID or URL. Expected a Docs ID or https://docs.google.com/document/d/... URL."
            )
        return resolved

    @staticmethod
    def _google_docs_extract_document_id(raw_value: str | None) -> str | None:
        if not raw_value:
            return None

        stripped = raw_value.strip()
        match = re.search(r"/document/d/([a-zA-Z0-9_-]+)", stripped)
        if match:
            return match.group(1)
        if re.fullmatch(r"[a-zA-Z0-9_-]{20,}", stripped):
            return stripped
        return None

    def _google_docs_load_document(self, document_id: str, readonly: bool) -> dict[str, Any]:
        return self._google_docs_service(readonly).documents().get(documentId=document_id).execute()

    @staticmethod
    def _google_docs_url(document_id: str) -> str:
        return f"https://docs.google.com/document/d/{document_id}/edit"

    @staticmethod
    def _google_docs_plain_text(document: dict[str, Any]) -> str:
        chunks: list[str] = []

        def walk_content(value: Any) -> None:
            if isinstance(value, list):
                for item in value:
                    walk_content(item)
                return
            if not isinstance(value, dict):
                return
            text_run = value.get("textRun")
            if isinstance(text_run, dict):
                content = text_run.get("content")
                if isinstance(content, str):
                    chunks.append(content)
            for nested_value in value.values():
                walk_content(nested_value)

        walk_content(document.get("body", {}).get("content", []))
        return "".join(chunks).strip()

    @staticmethod
    def _google_docs_body_end_index(document: dict[str, Any]) -> int:
        body_content = document.get("body", {}).get("content", [])
        if not body_content:
            return 1
        last_item = body_content[-1]
        end_index = last_item.get("endIndex")
        if not isinstance(end_index, int):
            return 1
        return max(1, end_index - 1)

    @classmethod
    def _google_docs_end_index(cls, document: dict[str, Any]) -> int:
        return cls._google_docs_body_end_index(document)

    def _google_docs_http_error(self, exc: HttpError) -> dict[str, Any]:
        status = getattr(exc.resp, "status", None)
        content = ""
        if getattr(exc, "content", None):
            try:
                content = exc.content.decode("utf-8", errors="ignore")[:500]
            except Exception:
                content = str(exc)[:500]

        if status == 404:
            return {
                "ok": False,
                "error": (
                    "Google Docs document tidak ditemukan. Pastikan document ID benar dan file itu "
                    "di-share ke email service account."
                ),
                "status": status,
                "details": content,
            }
        if status == 403:
            return {
                "ok": False,
                "error": (
                    "Akses Google Docs ditolak. Pastikan Google Docs API aktif dan dokumen target "
                    "sudah di-share ke email service account sebagai Editor."
                ),
                "status": status,
                "details": content,
            }

        return {
            "ok": False,
            "error": f"Google Docs API error: HTTP {status}",
            "status": status,
            "details": content or str(exc),
        }

    @staticmethod
    def _extract_notion_title(item: dict[str, Any]) -> str:
        properties = item.get("properties", {})
        title_value = properties.get("title")
        if title_value and title_value.get("title"):
            return "".join(part.get("plain_text", "") for part in title_value["title"])

        if item.get("object") == "page":
            for prop in properties.values():
                if prop.get("type") == "title":
                    return "".join(part.get("plain_text", "") for part in prop.get("title", []))
        return "Untitled"

    def _enabled_task_providers(self) -> list[str]:
        source = self.settings.dynamic_nagging_source
        providers: list[str] = []
        if source in {"auto", "local"} and (
            self.settings.daily_task_list_enabled or self._local_task_store_path().exists()
        ):
            providers.append("local")
        if source in {"auto", "notion"} and self.settings.notion_api_key and self.settings.notion_task_database_id:
            providers.append("notion")
        if source in {"auto", "todoist"} and self.settings.todoist_api_token:
            providers.append("todoist")
        if source in {"auto", "google_tasks"} and self.settings.google_tasks_tasklist_id:
            providers.append("google_tasks")
        return providers

    async def _local_list_urgent_tasks(
        self,
        now: datetime,
        deadline_before: datetime,
    ) -> list[dict[str, Any]]:
        async with self._local_task_lock:
            items = self._load_local_tasks_unlocked()

        tasks = []
        for item in items:
            if item.get("status") == "completed":
                continue

            deadline_at = self._parse_datetime(item.get("due"))
            if not deadline_at or deadline_at > deadline_before or deadline_at < now - timedelta(hours=1):
                continue

            task_id = str(item.get("id") or self._daily_task_key(deadline_at, item.get("title", "")))
            tasks.append(
                {
                    "task_key": f"local:{task_id}",
                    "source": "local",
                    "task_id": task_id,
                    "task_name": item.get("title") or "Local task",
                    "deadline_at": deadline_at,
                    "progress": item.get("notes", ""),
                    "status": item.get("status", "needsAction"),
                    "url": None,
                }
            )
        return tasks

    async def _notion_list_urgent_tasks(
        self,
        now: datetime,
        deadline_before: datetime,
    ) -> list[dict[str, Any]]:
        database_id = self.settings.notion_task_database_id
        if not database_id or not self.settings.notion_api_key:
            return []

        payload = {
            "page_size": 20,
            "filter": {
                "property": self.settings.notion_task_deadline_property,
                "date": {"on_or_before": deadline_before.isoformat()},
            },
            "sorts": [
                {
                    "property": self.settings.notion_task_deadline_property,
                    "direction": "ascending",
                }
            ],
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"https://api.notion.com/v1/databases/{database_id}/query",
                headers=self._notion_headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        tasks = []
        for item in data.get("results", []):
            properties = item.get("properties", {})
            deadline_at = self._notion_property_datetime(
                properties.get(self.settings.notion_task_deadline_property),
            )
            if not deadline_at or deadline_at > deadline_before or deadline_at < now - timedelta(hours=1):
                continue

            status = self._notion_property_text(properties.get(self.settings.notion_task_status_property))
            if status and status.lower() in self.settings.notion_task_done_values:
                continue

            title = self._notion_property_title(
                properties.get(self.settings.notion_task_title_property)
            ) or self._extract_notion_title(item)
            progress = self._notion_property_text(
                properties.get(self.settings.notion_task_progress_property)
            )
            tasks.append(
                {
                    "task_key": f"notion:{item.get('id')}",
                    "source": "notion",
                    "task_id": item.get("id"),
                    "task_name": title or "Untitled task",
                    "deadline_at": deadline_at,
                    "progress": progress,
                    "status": status,
                    "url": item.get("url"),
                }
            )
        return tasks

    async def _todoist_list_urgent_tasks(
        self,
        now: datetime,
        deadline_before: datetime,
    ) -> list[dict[str, Any]]:
        token = self.settings.todoist_api_token
        if not token:
            return []

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                "https://api.todoist.com/rest/v2/tasks",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            data = response.json()

        tasks = []
        for item in data:
            due = item.get("due") or {}
            deadline_at = self._todoist_due_to_datetime(due, now.tzinfo)
            if not deadline_at or deadline_at > deadline_before or deadline_at < now - timedelta(hours=1):
                continue
            tasks.append(
                {
                    "task_key": f"todoist:{item.get('id')}",
                    "source": "todoist",
                    "task_id": str(item.get("id")),
                    "task_name": item.get("content") or "Todoist task",
                    "deadline_at": deadline_at,
                    "progress": "",
                    "status": "needsAction",
                    "url": None,
                }
            )
        return tasks

    async def _google_tasks_list_urgent_tasks(
        self,
        now: datetime,
        deadline_before: datetime,
    ) -> list[dict[str, Any]]:
        service = self._google_tasks_service()
        if service is None:
            return []

        result = (
            service.tasks()
            .list(
                tasklist=self.settings.google_tasks_tasklist_id,
                showCompleted=False,
                showHidden=False,
                maxResults=100,
            )
            .execute()
        )

        tasks = []
        for item in result.get("items", []):
            if item.get("status") == "completed":
                continue
            deadline_at = self._parse_datetime(item.get("due"))
            if not deadline_at or deadline_at > deadline_before or deadline_at < now - timedelta(hours=1):
                continue
            tasks.append(
                {
                    "task_key": f"google_tasks:{item.get('id')}",
                    "source": "google_tasks",
                    "task_id": item.get("id"),
                    "task_name": item.get("title") or "Google Task",
                    "deadline_at": deadline_at,
                    "progress": item.get("notes", ""),
                    "status": item.get("status"),
                    "url": None,
                }
            )
        return tasks

    def _notion_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.notion_api_key}",
            "Notion-Version": self.settings.notion_version,
            "Content-Type": "application/json",
        }

    async def _notion_page_lines(self, page_id: str) -> list[str]:
        if not self.settings.notion_api_key:
            return []

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"https://api.notion.com/v1/blocks/{page_id}/children",
                headers=self._notion_headers(),
                params={"page_size": 20},
            )
            response.raise_for_status()
            data = response.json()

        lines: list[str] = []
        for block in data.get("results", []):
            block_type = block.get("type")
            if not block_type:
                continue
            block_data = block.get(block_type, {})
            rich_text = block_data.get("rich_text", [])
            text = "".join(part.get("plain_text", "") for part in rich_text).strip()
            if text:
                lines.append(text)
        return lines

    @staticmethod
    def _pick_best_notion_result(task_name: str, results: list[dict[str, Any]]) -> dict[str, Any]:
        query = task_name.strip().lower()

        def score(item: dict[str, Any]) -> tuple[int, int]:
            title = (item.get("title") or "").strip().lower()
            if title == query:
                return (3, len(title))
            if query and query in title:
                return (2, len(title))
            if title and title in query:
                return (1, len(title))
            return (0, len(title))

        return max(results, key=score)

    @staticmethod
    def _extract_context_and_target(lines: list[str]) -> tuple[str | None, str | None]:
        context = None
        target = None
        for line in lines:
            lowered = line.lower()
            normalized = ToolRegistry._strip_label(line)
            if not context and any(
                token in lowered for token in ("konteks", "context", "terakhir", "last update")
            ):
                context = normalized
                continue
            if not target and any(
                token in lowered for token in ("target", "malam ini", "tonight", "next step")
            ):
                target = normalized
                continue

        if not context and lines:
            context = ToolRegistry._strip_label(lines[0])
        if not target and len(lines) > 1:
            target = ToolRegistry._strip_label(lines[1])
        return context, target

    @staticmethod
    def _strip_label(text: str) -> str:
        cleaned = text.strip()
        for label in (
            "konteks terakhir:",
            "konteks:",
            "context:",
            "last update:",
            "target sekarang:",
            "target malam ini:",
            "target:",
            "tonight:",
            "next step:",
        ):
            if cleaned.lower().startswith(label):
                return cleaned[len(label):].strip()
        return cleaned

    def _google_tasks_service(self):
        service_account_file = (
            self.settings.google_tasks_service_account_file
            or self.settings.google_service_account_file
        )
        if not service_account_file or not self.settings.google_tasks_tasklist_id:
            return None

        credentials = service_account.Credentials.from_service_account_file(
            service_account_file,
            scopes=["https://www.googleapis.com/auth/tasks.readonly"],
        )
        if self.settings.google_tasks_impersonate_user:
            credentials = credentials.with_subject(self.settings.google_tasks_impersonate_user)
        return build("tasks", "v1", credentials=credentials, cache_discovery=False)

    def _local_task_store_path(self) -> Path:
        return Path(self.settings.local_task_store_file)

    def _load_local_tasks_unlocked(self) -> list[dict[str, Any]]:
        path = self._local_task_store_path()
        if not path.exists():
            return []
        try:
            raw = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            logger.exception("Failed to load local task store path=%s", path)
            return []
        if not isinstance(raw, list):
            return []
        return [item for item in raw if isinstance(item, dict)]

    def _save_local_tasks_unlocked(self, items: list[dict[str, Any]]) -> None:
        path = self._local_task_store_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(items, ensure_ascii=True, indent=2) + "\n")

    @staticmethod
    def _normalize_task_name(name: str) -> str:
        return " ".join(name.lower().split())

    def _daily_task_key(self, current: datetime, title: str) -> str:
        return f"{current.date().isoformat()}::{self._normalize_task_name(title)}"

    def _local_task_identity(self, item: dict[str, Any]) -> str | None:
        daily_key = item.get("daily_key")
        if isinstance(daily_key, str) and daily_key.strip():
            return daily_key.strip()

        title = str(item.get("title") or "").strip()
        due = self._parse_datetime(item.get("due"))
        if not title or not due:
            return None
        return f"{due.date().isoformat()}::{self._normalize_task_name(title)}"

    def _prune_local_tasks(
        self,
        items: list[dict[str, Any]],
        current: datetime,
    ) -> list[dict[str, Any]]:
        cutoff_date = current.date() - timedelta(days=14)
        kept: list[dict[str, Any]] = []
        for item in items:
            due = self._parse_datetime(item.get("due"))
            if due and due.date() < cutoff_date:
                continue
            kept.append(item)
        return kept

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=ZoneInfo(self.settings.timezone))
        return parsed.astimezone(ZoneInfo(self.settings.timezone))

    def _notion_property_datetime(self, prop: dict[str, Any] | None) -> datetime | None:
        if not prop:
            return None
        if prop.get("type") == "date":
            return self._parse_datetime((prop.get("date") or {}).get("start"))
        return None

    @staticmethod
    def _notion_property_title(prop: dict[str, Any] | None) -> str:
        if not prop:
            return ""
        if prop.get("type") != "title":
            return ""
        return "".join(part.get("plain_text", "") for part in prop.get("title", []))

    @staticmethod
    def _notion_property_text(prop: dict[str, Any] | None) -> str:
        if not prop:
            return ""
        prop_type = prop.get("type")
        if prop_type == "status":
            return (prop.get("status") or {}).get("name", "")
        if prop_type == "select":
            return (prop.get("select") or {}).get("name", "")
        if prop_type == "multi_select":
            return ", ".join(item.get("name", "") for item in prop.get("multi_select", []))
        if prop_type == "rich_text":
            return "".join(part.get("plain_text", "") for part in prop.get("rich_text", []))
        if prop_type == "number":
            value = prop.get("number")
            return "" if value is None else str(value)
        if prop_type == "checkbox":
            return "done" if prop.get("checkbox") else ""
        if prop_type == "formula":
            formula = prop.get("formula") or {}
            value = formula.get(formula.get("type"))
            return "" if value is None else str(value)
        return ""

    @staticmethod
    def _todoist_due_to_datetime(due: dict[str, Any], tzinfo) -> datetime | None:
        if not due:
            return None
        if due.get("datetime"):
            try:
                parsed = datetime.fromisoformat(due["datetime"].replace("Z", "+00:00"))
            except ValueError:
                return None
            return parsed.astimezone(tzinfo)
        if due.get("date"):
            try:
                parsed = datetime.fromisoformat(f"{due['date']}T23:59:00")
            except ValueError:
                return None
            return parsed.replace(tzinfo=tzinfo)
        return None
