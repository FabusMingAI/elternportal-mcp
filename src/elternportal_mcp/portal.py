"""Bounded, same-origin HTTPS access with one isolated session per refresh."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any
from urllib.parse import urljoin, urlsplit

import aiohttp
from bs4 import BeautifulSoup

from .config import School, Settings
from .storage import now
from .vendor.parsers import PortalParsers, parse_teachers, portal_appointment
from .vendor.timetable import parse_course_registrations

MAX_PAGE_BYTES = 4 * 1024 * 1024
MAX_DOCUMENT_BYTES = 25 * 1024 * 1024
SECTIONS = (
    "appointment",
    "letter",
    "message",
    "blackboard",
    "poll",
    "lesson",
    "substitution",
    "sicknote",
    "register",
)


class PortalError(Exception):
    """Only static error codes cross the MCP boundary."""


class AuthenticationRequired(PortalError):
    pass


def safe_url(base: str, target: str) -> str:
    result = urljoin(base, target)
    left, right = urlsplit(base), urlsplit(result)
    if (
        right.scheme != "https"
        or right.hostname != left.hostname
        or right.port not in (None, 443)
        or right.username
        or right.password
    ):
        raise PortalError("cross_origin_request_blocked")
    return result


@dataclass
class Response:
    data: bytes
    headers: Any
    status: int = 200

    async def text(self):
        return self.data.decode("utf-8", errors="replace")

    async def json(self, **kwargs):
        return json.loads(await self.text())

    def raise_for_status(self):
        if self.status >= 400:
            raise PortalError(f"http_{self.status}")


def inspect_html(path: str, body: str):
    soup = BeautifulSoup(body, "html.parser")
    if soup.select_one(".form-signin, input[type=password]"):
        raise AuthenticationRequired("authentication_required_or_mfa")
    if path.startswith("/api/"):
        return
    selectors = {
        "/service/stundenplan": "#asam_content div.table-responsive table",
        "/service/vertretungsplan": "#asam_content .main_center",
        "/aktuelles/elternbriefe": ".link_nachrichten, #asam_content table",
        "/meldungen/kommunikation_fachlehrer": "#messages-fachlehrer-table",
        "/meldungen/krankmeldung": "div.content table.ui",
        "/service/klassenbuch": "#asam_content table.table-bordered",
    }
    selector = selectors.get(path)
    if selector and not soup.select_one(selector):
        raise PortalError("unrecognized_or_disabled_section")
    if not selector and not soup.select_one("#asam_content, #message-thread-grid"):
        raise PortalError("unrecognized_page_layout")


class PortalHTTP:
    def __init__(self, session: aiohttp.ClientSession, base: str):
        self.session, self.base = session, base
        self.authenticated = False

    @asynccontextmanager
    async def request(self, method: str, url: str, *, document: bool = False, **kwargs):
        url = safe_url(self.base, url)
        limit = MAX_DOCUMENT_BYTES if document else MAX_PAGE_BYTES
        for _ in range(6):
            async with self.session.request(
                method, url, allow_redirects=False, **kwargs
            ) as response:
                if response.status in (301, 302, 303, 307, 308):
                    target = response.headers.get("Location")
                    if not target:
                        raise PortalError("invalid_redirect")
                    url = safe_url(url, target)
                    if response.status == 303 or (
                        response.status in (301, 302) and method == "POST"
                    ):
                        method, kwargs = "GET", {}
                    continue
                if response.status in (401, 403):
                    raise AuthenticationRequired("authentication_required_or_forbidden")
                if response.status != 200:
                    raise PortalError(f"http_{response.status}")
                if (response.content_length or 0) > limit:
                    raise PortalError("response_too_large")
                data = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    data.extend(chunk)
                    if len(data) > limit:
                        raise PortalError("response_too_large")
                buffered = Response(bytes(data), dict(response.headers))
                content_type = response.headers.get("Content-Type", "")
                if self.authenticated and not document:
                    body = await buffered.text()
                    path = urlsplit(url).path
                    if body.lstrip().startswith("<") or "text/html" in content_type:
                        # The appointment API returns JSON with a text/html MIME type.
                        if not body.lstrip().startswith(("{", "[")):
                            inspect_html(path, body)
                yield buffered
                return
        raise PortalError("too_many_redirects")

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)


class Portal(PortalParsers):
    def __init__(self, http: PortalHTTP, school: School, settings: Settings):
        super().__init__(http)
        self.set_config(school.school, school.username, school.password().get_secret_value())
        self.set_option(**dict.fromkeys(SECTIONS, True))
        self.set_option_threshold(
            blackboard_threshold=-settings.lookback_days,
            letter_threshold=-settings.lookback_days,
            message_threshold=-settings.lookback_days,
            poll_threshold=-settings.lookback_days,
            sicknote_threshold=-max(settings.lookback_days, 366),
        )
        # Five school days are fetched on demand as part of a refresh.
        self.set_option_register(register_start_min=0, register_start_max=4)
        self._letter_links = {}
        self._extra_messages = []
        self._blackboard_items = []
        self._timetable = []
        self._subst = {}


def serializable(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serializable(v) for v in value]
    return value


def error_code(error: Exception) -> str:
    if isinstance(error, PortalError):
        return str(error)
    if isinstance(error, (TimeoutError, aiohttp.ClientError)):
        return "connection_failed"
    return "parser_or_authentication_error"


class PortalBackend:
    def __init__(self, settings: Settings):
        self.settings = settings

    @asynccontextmanager
    async def login(self, school: School):
        timeout = aiohttp.ClientTimeout(
            total=self.settings.request_timeout_seconds,
            connect=min(10, self.settings.request_timeout_seconds),
        )
        async with aiohttp.ClientSession(
            timeout=timeout,
            headers={
                "User-Agent": "elternportal-mcp-bavaria/0.2.0",
            },
        ) as session:
            http = PortalHTTP(session, f"https://{school.school}.eltern-portal.org/")
            api = Portal(http, school, self.settings)
            suffix = "demo" if school.school == "demo" else "online"
            await getattr(api, f"async_base_{suffix}")()
            await getattr(api, f"async_login_{suffix}")()
            http.authenticated = True
            try:
                yield api, http, suffix
            finally:
                http.authenticated = False
                if suffix == "online":
                    try:
                        await api.async_logout_online()
                    except Exception:
                        pass  # Session is closed regardless; no raw portal error is logged.

    async def fetch(self, school: School) -> dict:
        async with self.login(school) as (api, http, suffix):
            children = []
            for student in api.students:
                api._student = student
                await getattr(api, f"async_set_child_{suffix}")()
                statuses = {}
                for name in SECTIONS:
                    try:
                        async with asyncio.timeout(180):
                            await getattr(api, f"async_{name}_{suffix}")()
                        statuses[name] = {"status": "ok", "fetched_at": now()}
                    except AuthenticationRequired:
                        raise
                    except Exception as error:
                        statuses[name] = {"status": "unavailable", "error": error_code(error)}
                registrations = None
                if suffix != "demo":
                    try:
                        async with http.get(
                            urljoin(api.base_url, "/buchungen/intensivierungskurse")
                        ) as response:
                            registrations = parse_course_registrations(await response.text())
                    except AuthenticationRequired:
                        raise
                    except Exception:
                        pass  # Optional existing registrations, never submit the form.
                items = []
                # Failed sections never accidentally expose partially parsed records.
                groups = {"letter": "letters", "poll": "polls"}
                for name, attr in groups.items():
                    if statuses[name]["status"] != "ok":
                        setattr(student, attr, [])
                if statuses["message"]["status"] != "ok":
                    api._extra_messages = []
                if statuses["blackboard"]["status"] != "ok":
                    api._blackboard_items = []
                for item in api._collect_items():
                    row = asdict(item)
                    row.pop("files", None)
                    row["id"] = row.pop("uid")
                    row["child_id"] = f"{school.school}:{student.student_id}"
                    items.append(row)
                appointments = (
                    [
                        portal_appointment(
                            f"{school.school}-{student.student_id}-appointment-{a.appointment_id}",
                            a.short,
                            a.title,
                            a.classname,
                            a.start,
                            a.end,
                        )
                        for a in student.appointments
                    ]
                    if statuses["appointment"]["status"] == "ok"
                    else []
                )
                registers = (
                    [
                        {
                            k: getattr(r, k, None)
                            for k in (
                                "subject",
                                "teacher",
                                "lesson",
                                "rtype",
                                "start",
                                "completion",
                                "body",
                            )
                        }
                        for r in student.registers
                    ]
                    if statuses["register"]["status"] == "ok"
                    else []
                )
                sicknotes = (
                    [
                        {"start": s.start, "end": s.end, "comment": s.comment}
                        for s in student.sicknotes
                    ]
                    if statuses["sicknote"]["status"] == "ok"
                    else []
                )
                children.append(
                    {
                        "id": f"{school.school}:{student.student_id}",
                        "school": school.school,
                        "student_id": student.student_id,
                        "name": student.fullname,
                        "class_name": student.classname,
                        "course_registrations": registrations,
                        "sections": statuses,
                        "items": items,
                        "appointments": appointments,
                        "timetable": api._timetable if statuses["lesson"]["status"] == "ok" else [],
                        "substitutions": api._subst
                        if statuses["substitution"]["status"] == "ok"
                        else {},
                        "sicknotes": sicknotes,
                        "register": registers,
                    }
                )
            teachers, teacher_status = {}, {"status": "demo" if suffix == "demo" else "ok"}
            if suffix != "demo":
                try:
                    async with http.get(
                        urljoin(api.base_url, "/service/schulinformationen")
                    ) as response:
                        parsed = parse_teachers(await response.text())
                        if parsed is None:
                            raise PortalError("teacher_list_not_available")
                        teachers = parsed
                except AuthenticationRequired:
                    raise
                except Exception as error:
                    teacher_status = {"status": "unavailable", "error": error_code(error)}
            return serializable(
                {
                    "school": school.school,
                    "school_name": api.school_name,
                    "fetched_at": now(),
                    "children": children,
                    "teachers": teachers,
                    "teacher_status": teacher_status,
                }
            )

    async def download(
        self,
        school: School,
        child: dict,
        item_id: str,
        index: int,
        kind: str,
        pdf_only: bool = True,
    ) -> bytes:
        # Re-login and rediscover the attachment in the selected child's fresh page;
        # never trust a cached CSRF link or an arbitrary URL supplied by an MCP caller.
        async with self.login(school) as (api, http, suffix):
            api._student = next(
                (s for s in api.students if s.student_id == child["student_id"]), None
            )
            if api._student is None:
                raise PortalError("child_not_found")
            await getattr(api, f"async_set_child_{suffix}")()
            if kind not in ("letter", "message", "blackboard", "poll"):
                raise PortalError("unsupported_attachment_kind")
            await getattr(api, f"async_{kind}_{suffix}")()
            item = next((i for i in api._collect_items() if i.uid == item_id), None)
            if item is None or not 0 <= index < len(item.attachments):
                raise PortalError("attachment_not_found")
            url = safe_url(api.base_url, item.attachments[index].href)
            async with http.get(url, document=True) as response:
                if pdf_only and not response.data.startswith(b"%PDF-"):
                    raise PortalError("attachment_is_not_pdf")
                if response.data.lstrip().startswith((b"<html", b"<!DOCTYPE html")):
                    raise PortalError("attachment_returned_html")
                return response.data
