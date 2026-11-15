"""Application API shared by MCP tools, independent of the protocol layer."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import sys
import time
from datetime import UTC, date, datetime

from . import demo
from .bridge import Bridge
from .config import Settings
from .organizer import Organizer
from .portal import PortalBackend, error_code
from .storage import Store, now
from .vendor.classes import concerns_class

KINDS = {"letter", "message", "blackboard", "poll"}
SECTION_FIELDS = {
    "appointment": "appointments",
    "lesson": "timetable",
    "substitution": "substitutions",
    "sicknote": "sicknotes",
    "register": "register",
}


def iso_day(value: str | None):
    if value is not None:
        date.fromisoformat(value)
    return value


def page(rows: list, offset: int = 0, limit: int = 50) -> dict:
    if offset < 0 or not 1 <= limit <= 100:
        raise ValueError("offset >= 0 and 1 <= limit <= 100 required")
    end = offset + limit
    return {
        "entries": rows[offset:end],
        "total": len(rows),
        "next_offset": end if end < len(rows) else None,
    }


class Service(Organizer):
    def __init__(self, settings: Settings, backend=None):
        self.settings = settings
        self.store = Store(settings.data_dir)
        self.backend = backend or PortalBackend(settings)
        self.bridge = Bridge(settings.home_assistant)
        self.notification_lock = asyncio.Lock()
        self.schools = {s.school: s for s in settings.schools}
        self.locks = {s: asyncio.Lock() for s in self.schools}
        self.last_attempt: dict[str, float] = {}
        self.failures: dict[str, str] = {}

    def school(self, code: str):
        if code not in self.schools:
            raise ValueError("School not configured")
        return self.schools[code]

    def metadata(self, snapshot: dict) -> dict:
        stamp = snapshot["fetched_at"]
        age = max(0, int((datetime.now(UTC) - datetime.fromisoformat(stamp)).total_seconds()))
        return {
            "school": snapshot["school"],
            "fetched_at": stamp,
            "age_seconds": age,
            "stale": age > self.settings.cache_ttl_seconds
            or snapshot["school"] in self.failures
            or bool(snapshot.get("refresh_error")),
            "refresh_error": self.failures.get(snapshot["school"], snapshot.get("refresh_error")),
            "data_is_untrusted": True,
        }

    async def snapshot(self, code: str, *, refresh: bool = False) -> dict:
        school = self.school(code)
        async with self.locks[code]:
            cached = self.store.get("snapshots", code)
            if cached and not refresh and not self.metadata(cached)["stale"]:
                self.ingest_snapshot(cached)
                return cached
            if code in self.last_attempt and time.monotonic() - self.last_attempt[code] < 60:
                if cached:
                    self.ingest_snapshot(cached)
                    return cached
                raise ValueError("Refresh throttled; retry after 60 seconds")
            self.last_attempt[code] = time.monotonic()
            try:
                async with asyncio.timeout(300):
                    fresh = demo.snapshot() if code == "demo" else await self.backend.fetch(school)
                if cached:
                    fresh = self.merge(cached, fresh)
                self.store.put("snapshots", code, fresh)
                self.ingest_snapshot(fresh)
                self.failures.pop(code, None)
                return fresh
            except Exception as error:
                self.failures[code] = error_code(error)
                if cached:
                    cached["refresh_error"] = self.failures[code]
                    self.store.put("snapshots", code, cached)
                    return cached
                raise ValueError(f"Portal unavailable: {self.failures[code]}") from None

    @staticmethod
    def merge(old: dict, fresh: dict) -> dict:
        """Retain failed sections with their own original timestamp and stale flag."""
        previous = {c["id"]: c for c in old["children"]}
        for child in fresh["children"]:
            prior = previous.get(child["id"])
            if prior is None:
                continue
            for section, state in child["sections"].items():
                if state["status"] == "ok":
                    continue
                state["retained"] = True
                state["fetched_at"] = prior["sections"].get(section, {}).get("fetched_at")
                if section in SECTION_FIELDS:
                    child[SECTION_FIELDS[section]] = copy.deepcopy(prior[SECTION_FIELDS[section]])
                elif section in KINDS:
                    child["items"].extend(
                        copy.deepcopy([i for i in prior["items"] if i["kind"] == section])
                    )
        if fresh["teacher_status"]["status"] == "unavailable":
            fresh["teachers"] = old["teachers"]
            fresh["teacher_status"].update(
                retained=True, fetched_at=old["teacher_status"].get("fetched_at", old["fetched_at"])
            )
        return fresh

    async def child(self, child_id: str) -> tuple[dict, dict]:
        if ":" not in child_id:
            raise ValueError("Use the exact child_id from list_children")
        code = child_id.split(":", 1)[0]
        snapshot = await self.snapshot(code)
        child = next((c for c in snapshot["children"] if c["id"] == child_id), None)
        if child is None:
            raise ValueError("Child not found")
        return snapshot, child

    async def children(self, school: str | None = None) -> dict:
        codes = [school] if school else list(self.schools)
        entries, sources = [], []
        for code in codes:
            try:
                snapshot = await self.snapshot(code)
                entries.extend(
                    {k: c[k] for k in ("id", "school", "name", "class_name")}
                    for c in snapshot["children"]
                )
                sources.append(self.metadata(snapshot))
            except ValueError:
                if code not in self.schools:
                    raise
                sources.append({"school": code, "error": self.failures.get(code, "unavailable")})
        return {"children": entries, "sources": sources}

    async def items(
        self,
        child_id: str,
        kind: str | None = None,
        query: str = "",
        since: str | None = None,
        until: str | None = None,
        offset: int = 0,
        limit: int = 50,
        read: bool | None = None,
        include_archived: bool = False,
    ) -> dict:
        if kind is not None and kind not in KINDS:
            raise ValueError("Unknown item kind")
        iso_day(since), iso_day(until)
        if since and until and since > until:
            raise ValueError("since must be <= until")
        snapshot, child = await self.child(child_id)
        rows = []
        candidates = (
            [i for i in self.store.records("history") if i["child_id"] == child_id]
            if include_archived
            else child["items"]
        )
        for item in candidates:
            state = self.store.get("item_states", item["id"]) or {"status": "open", "read": False}
            if not include_archived and state.get("archived"):
                continue
            if read is not None and state.get("read", False) != read:
                continue
            if kind and item["kind"] != kind:
                continue
            stamp = (item.get("sent") or "")[:10]
            if (since and (not stamp or stamp < since)) or (until and (not stamp or stamp > until)):
                continue
            documents = [
                self.store.get("documents", f"{item['id']}:{n}")
                for n in range(len(item["attachments"]))
            ]
            text = " ".join([item["title"], item["body"], *[d["text"] for d in documents if d]])
            if query.casefold() not in text.casefold():
                continue
            rows.append(
                {
                    "id": item["id"],
                    "kind": item["kind"],
                    "title": item["title"],
                    "sent": item["sent"],
                    "sender": item.get("sender"),
                    "attachment_count": len(item["attachments"]),
                    "meta": item["meta"],
                    "local_state": self.store.get("item_states", item["id"]) or {"status": "open"},
                    "analysis": self.store.get("analyses", item["id"]),
                }
            )
        rows.sort(key=lambda r: (r["sent"] or "", r["id"]), reverse=True)
        return {
            **page(rows, offset, limit),
            "source": self.metadata(snapshot),
            "sections": child["sections"],
        }

    async def item(self, child_id: str, item_id: str) -> tuple[dict, dict, dict]:
        snapshot, child = await self.child(child_id)
        item = next((i for i in child["items"] if i["id"] == item_id), None)
        if item is None:
            item = self.store.get("history", item_id)
            if item is None or item["child_id"] != child_id:
                raise ValueError("Item not found for this child")
        return snapshot, child, item

    async def get_item(
        self, child_id: str, item_id: str, max_chars: int = 12000, offset: int = 0
    ) -> dict:
        if not 1 <= max_chars <= 30000 or offset < 0:
            raise ValueError("Invalid text page bounds")
        snapshot, child, item = await self.item(child_id, item_id)
        row = {k: v for k, v in item.items() if k not in ("attachments", "body")}
        # No session-dependent URLs are returned to the model.
        row["attachments"] = [
            {
                "index": n,
                "name": a["name"],
                "cached": self.store.get("documents", f"{item_id}:{n}") is not None,
            }
            for n, a in enumerate(item["attachments"])
        ]
        body = item["body"]
        row.update(
            body=body[offset : offset + max_chars],
            total_chars=len(body),
            next_offset=offset + max_chars if offset + max_chars < len(body) else None,
        )
        return {
            "item": row,
            "source": self.metadata(snapshot),
            "section": child["sections"].get(item["kind"]),
            "local_state": self.store.get("item_states", item_id),
            "analysis": self.store.get("analyses", item_id),
        }

    async def section(self, child_id: str, section: str) -> dict:
        snapshot, child = await self.child(child_id)
        return {
            "data": self.enriched_timetable(snapshot, child)
            if section == "lesson"
            else child[SECTION_FIELDS[section]],
            "section": child["sections"][section],
            "source": self.metadata(snapshot),
        }

    async def appointments(
        self,
        child_id: str,
        since: str | None = None,
        until: str | None = None,
        own_class_only: bool = True,
        offset: int = 0,
        limit: int = 50,
    ) -> dict:
        iso_day(since), iso_day(until)
        if since and until and since > until:
            raise ValueError("since must be <= until")
        snapshot, child = await self.child(child_id)
        rows = []
        for row in child["appointments"]:
            start = (row.get("start") or "")[:10]
            end = (row.get("end") or start)[:10]
            if (since and end < since) or (until and start > until):
                continue
            if own_class_only and concerns_class(row["title"], child["class_name"]) is False:
                continue
            rows.append(row)
        rows.sort(key=lambda r: r.get("start") or "")
        return {
            **page(rows, offset, limit),
            "section": child["sections"]["appointment"],
            "source": self.metadata(snapshot),
        }

    async def download(
        self, child_id: str, item_id: str, attachment_index: int, confirm_possible_receipt: bool
    ) -> dict:
        if not self.settings.allow_pdf_downloads:
            raise ValueError(
                "PDF downloads disabled; enable allow_pdf_downloads in local configuration"
            )
        if not confirm_possible_receipt:
            raise ValueError(
                "Downloading may confirm receipt at school; explicit confirmation required"
            )
        snapshot, child, item = await self.item(child_id, item_id)
        if not 0 <= attachment_index < len(item["attachments"]):
            raise ValueError("Attachment not found")
        code = child["school"]
        async with self.locks[code]:
            try:
                async with asyncio.timeout(180):
                    data = await self.backend.download(
                        self.school(code), child, item_id, attachment_index, item["kind"]
                    )
                original = self.save_original_attachment(child, item, attachment_index, data)
                result = await self.extract_pdf(data)
            except Exception:
                raise ValueError(
                    "PDF download or extraction failed; receipt may already have been confirmed. Check the portal before retrying."
                ) from None
            finally:
                self.failures[code] = "refresh_needed_after_download"
                snapshot["refresh_error"] = "refresh_needed_after_download"
                self.store.put("snapshots", code, snapshot)
                self.last_attempt.pop(code, None)
            key = f"{item_id}:{attachment_index}"
            self.store.put(
                "documents",
                key,
                {
                    **result,
                    "item_id": item_id,
                    "item_version": item.get("version"),
                    "retrieved_at": now(),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "receipt_may_have_been_confirmed": True,
                },
            )
            # Force the next fetch to recheck the portal state after the download.
            return {
                **original,
                "cached": True,
                "pages": result["pages"],
                "ocr_required": result["ocr_required"],
                "receipt_may_have_been_confirmed": True,
                "next": "Use get_cached_document to read the locally extracted text",
            }

    @staticmethod
    async def extract_pdf(data: bytes) -> dict:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "elternportal_mcp.pdf",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            output, _ = await asyncio.wait_for(process.communicate(data), timeout=15)
        except BaseException:
            process.kill()
            await process.wait()
            raise
        if process.returncode:
            raise ValueError("pdf_extraction_failed")
        result = json.loads(output)
        if "error" in result:
            raise ValueError(result["error"])
        return result

    async def cached_document(
        self, child_id: str, item_id: str, index: int = 0, offset: int = 0, max_chars: int = 12000
    ) -> dict:
        # Authorization and cached text reading require no new portal request.
        code = child_id.split(":", 1)[0]
        self.school(code)
        snapshot = self.store.get("snapshots", code)
        child = next((c for c in (snapshot or {}).get("children", []) if c["id"] == child_id), None)
        item = next((i for i in (child or {}).get("items", []) if i["id"] == item_id), None)
        if not item:
            raise ValueError("Item not found for this child")
        if offset < 0 or not 1 <= max_chars <= 30000:
            raise ValueError("Invalid text page bounds")
        doc = self.store.get("documents", f"{item_id}:{index}")
        if doc is None:
            return {"cached": False, "download_performed": False}
        text = doc["text"]
        return {
            **{k: v for k, v in doc.items() if k != "text"},
            "cached": True,
            "text": text[offset : offset + max_chars],
            "total_chars": len(text),
            "next_offset": offset + max_chars if offset + max_chars < len(text) else None,
            "version_matches": doc.get("item_version") == item.get("version"),
            "data_is_untrusted": True,
            "download_performed": False,
        }
