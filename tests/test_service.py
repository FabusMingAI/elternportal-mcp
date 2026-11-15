import asyncio
import copy
import io
import os

import pytest
from pypdf import PdfWriter

from elternportal_mcp.config import School, Settings
from elternportal_mcp.portal import PortalError
from elternportal_mcp.service import Service
from elternportal_mcp.storage import Store


async def test_child_isolation_pagination_and_search(demo_service):
    service = demo_service
    children = await service.children()
    assert len(children["children"]) == 2
    first = await service.items("demo:1", limit=1)
    second = await service.items("demo:1", offset=1, limit=1)
    assert first["next_offset"] == 1
    assert first["entries"][0]["id"] != second["entries"][0]["id"]
    assert (await service.items("demo:1", query="WASSERFARBEN"))["total"] == 1
    with pytest.raises(ValueError, match="not found"):
        await service.get_item("demo:2", "demo-1-letter-1")
    with pytest.raises(ValueError):
        await service.items("demo:1", since="2026-99-01")
    assert (await service.items("demo:1", since="2099-01-01"))["total"] == 0


async def test_concurrent_refreshes_are_coalesced(live_service):
    service, backend = live_service
    await asyncio.gather(*(service.snapshot("testschool", refresh=True) for _ in range(10)))
    assert backend.fetches == 1
    assert (await service.children())["children"][0]["id"] == "testschool:1"


async def test_outage_survives_restart_without_leaking_exception(live_service, tmp_path):
    service, backend = live_service
    before = await service.snapshot("testschool")
    service.last_attempt.clear()
    backend.error = RuntimeError("SECRET-PASSWORD and private URL")
    after = await service.snapshot("testschool", refresh=True)
    assert after["children"] == before["children"]
    assert service.metadata(after)["stale"]
    assert "SECRET" not in str(service.metadata(after))
    restarted = Service(Settings(schools=[School(school="testschool")], data_dir=tmp_path), backend)
    try:
        assert restarted.metadata(restarted.store.get("snapshots", "testschool"))["stale"]
    finally:
        restarted.store.close()


async def test_partial_failures_retain_only_failed_sections(live_service):
    service, backend = live_service
    before = await service.snapshot("testschool")
    service.last_attempt.clear()
    backend.value["children"][0]["sections"]["lesson"] = {
        "status": "unavailable",
        "error": "http_404",
    }
    backend.value["children"][0]["timetable"] = []
    backend.value["children"][0]["items"] = []  # successful empty inbox must clear old entries
    after = await service.snapshot("testschool", refresh=True)
    child = after["children"][0]
    assert child["timetable"] == before["children"][0]["timetable"]
    assert child["sections"]["lesson"]["retained"]
    assert child["sections"]["lesson"]["fetched_at"]
    assert child["items"] == []


async def test_item_reads_cannot_download_or_confirm_receipt(live_service):
    service, backend = live_service
    backend.value["children"][0]["items"][0]["attachments"] = [
        {"name": "letter.pdf", "href": "/file?csrf=SECRET"}
    ]
    result = await service.get_item("testschool:1", "demo-1-letter-1")
    assert result["item"]["attachments"][0] == {"index": 0, "name": "letter.pdf", "cached": False}
    assert "SECRET" not in str(result)
    assert (await service.cached_document("testschool:1", "demo-1-letter-1"))["cached"] is False
    assert backend.downloads == 0
    with pytest.raises(ValueError, match="explicit confirmation"):
        await service.download("testschool:1", "demo-1-letter-1", 0, False)
    assert backend.downloads == 0


async def test_download_dual_gate_and_failure_marks_state_uncertain(live_service):
    service, backend = live_service
    backend.value["children"][0]["items"][0]["attachments"] = [
        {"name": "letter.pdf", "href": "/file"}
    ]
    await service.snapshot("testschool")
    with pytest.raises(ValueError, match="receipt may already"):
        await service.download("testschool:1", "demo-1-letter-1", 0, True)
    assert backend.downloads == 1
    assert service.metadata(service.store.get("snapshots", "testschool"))["stale"]
    service.settings = Settings(
        schools=[School(school="testschool")], data_dir=service.settings.data_dir
    )
    with pytest.raises(ValueError, match="disabled"):
        await service.download("testschool:1", "demo-1-letter-1", 0, True)
    assert backend.downloads == 1


async def test_pdf_worker_and_cache_do_not_redownload(live_service):
    service, backend = live_service
    buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(buffer)
    backend.pdf = buffer.getvalue()
    backend.value["children"][0]["items"][0]["attachments"] = [
        {"name": "letter.pdf", "href": "/file"}
    ]
    result = await service.download("testschool:1", "demo-1-letter-1", 0, True)
    assert result["ocr_required"]
    assert result["receipt_may_have_been_confirmed"]
    fetches = backend.fetches
    doc = await service.cached_document("testschool:1", "demo-1-letter-1")
    assert doc["cached"] and doc["pages"] == 1 and doc["version_matches"]
    assert backend.fetches == fetches and backend.downloads == 1


def test_task_persistence_and_file_permissions(tmp_path):
    store = Store(tmp_path)
    task = store.add_task("demo:1", "Bring water", due="2026-11-20", amount_cents=1250)
    store.close()
    reopened = Store(tmp_path)
    assert reopened.tasks("demo:1")[0] == task
    assert reopened.tasks("demo:2") == []
    with pytest.raises(ValueError):
        reopened.get("tasks; DROP TABLE tasks", "x")
    if os.name == "posix":
        assert (tmp_path / "state.sqlite3").stat().st_mode & 0o777 == 0o600
    reopened.close()


def test_merge_does_not_mutate_old_snapshot(demo_service):
    from elternportal_mcp.demo import snapshot

    old, fresh = snapshot(), snapshot()
    backup = copy.deepcopy(old)
    fresh["children"][0]["sections"]["letter"] = {"status": "unavailable"}
    fresh["children"][0]["items"] = []
    merged = Service.merge(old, fresh)
    assert merged["children"][0]["items"][0]["kind"] == "letter"
    assert old == backup


async def test_first_failure_is_sanitized_and_rate_limited(live_service):
    service, backend = live_service
    backend.error = PortalError("connection_failed")
    with pytest.raises(ValueError, match="connection_failed"):
        await service.snapshot("testschool")
    with pytest.raises(ValueError, match="throttled"):
        await service.snapshot("testschool")
    assert backend.fetches == 1
