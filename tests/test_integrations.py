import asyncio
import copy
import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from mcp.types import CreateMessageResult, TextContent
from pydantic import ValidationError

from elternportal_mcp.bridge import Bridge
from elternportal_mcp.config import HomeAssistant
from elternportal_mcp.features import model_result
from elternportal_mcp.server import create_server


@pytest.mark.parametrize(
    "kwargs",
    [
        {"url": "http://ha.local:8123"},
        {"url": "https://user:secret@ha.example"},
        {"url": "https://ha.example/path"},
        {"url": "https://ha.example", "notify_services": ["light.turn_on"]},
        {"url": "https://ha.example", "webuntis_calendars": {"demo:1": "../evil"}},
    ],
)
def test_bridge_configuration_rejects_unsafe_targets(kwargs):
    with pytest.raises(ValidationError):
        HomeAssistant(**kwargs)


async def test_sampling_is_scoped_and_bad_responses_are_sanitized(demo_service):
    response = CreateMessageResult(
        role="assistant",
        content=TextContent(type="text", text='{"summary":"Demo"}'),
        model="synthetic",
    )
    callback = AsyncMock(return_value=response)
    ctx = SimpleNamespace(session=SimpleNamespace(create_message=callback))
    assert (await model_result(ctx, demo_service, "Synthetic prompt", "sampling"))[
        "summary"
    ] == "Demo"
    assert callback.call_args.kwargs["include_context"] == "none"
    callback.side_effect = RuntimeError("secret-password-in-error")
    with pytest.raises(ValueError, match="sampling unavailable") as exc:
        await model_result(ctx, demo_service, "Prompt", "sampling")
    assert "secret-password" not in str(exc.value)


async def test_partial_push_retry_and_daily_deduplication(demo_service):
    service = demo_service
    service.bridge = Bridge(
        HomeAssistant(
            url="https://ha.example", notify_services=["notify.phone_a", "notify.phone_b"]
        )
    )
    calls = []

    async def request(method, path, data):
        calls.append((path, data))
        if path.endswith("phone_b") and len(calls) == 2:
            raise ValueError("Simulated failure")
        return []

    service.bridge.request = request
    first = await service.send_notification("digest")
    assert first["failed"] == ["notify.phone_b"]
    second = await service.send_notification("digest")
    assert not second["failed"]
    assert [c[0].rsplit("/", 1)[-1] for c in calls] == ["phone_a", "phone_b", "phone_b"]
    assert not (await service.send_notification("digest"))["sent"]


async def test_notification_gate_buttons_and_local_actions(demo_service, monkeypatch):
    service = demo_service
    await service.children()
    clock = datetime(2026, 11, 16, 18, 30, tzinfo=ZoneInfo("Europe/Berlin"))
    monkeypatch.setattr(service, "local_now", lambda: clock)
    task = service.store.add_task("demo:1", "Bring water", due="2026-11-16")
    sender = AsyncMock(return_value={"delivered": ["notify.demo"], "failed": []})
    service.bridge.send = sender
    mcp = create_server(service)
    with pytest.raises(Exception, match="confirmation"):
        await mcp.call_tool("send_briefing", {})
    assert sender.await_count == 0
    assert (await service.send_notification("reminders"))["sent"]
    actions = sender.call_args.kwargs["actions"]
    assert actions[0]["action"] == "ELTERNPORTAL_DONE:" + task["id"]
    assert service.handle_mobile_action(actions[1]["action"])
    assert service.store.get("tasks", task["id"])["snoozed_until"] == "2026-11-17"
    assert not service.handle_mobile_action("UNRELATED:action")
    assert service.handle_mobile_action(actions[0]["action"])
    assert service.store.get("tasks", task["id"])["status"] == "done"


async def test_webuntis_merge_and_failure_retention(demo_service):
    service = demo_service
    snapshot = await service.snapshot("demo")
    snapshot["children"][0]["timetable"][0].update(lesson="3", start="10:00", end="10:45")
    snapshot["children"][0]["substitutions"]["days"][0]["date"] = "2026-11-16"
    service.store.put("snapshots", "demo", snapshot)
    event = {
        "start": "2026-11-16T10:00:00+01:00",
        "end": "2026-11-16T10:45:00+01:00",
        "summary": "Cancelled: M",
        "description": json.dumps({"id": 12, "code": "cancelled", "subjects": [{"name": "M"}]}),
    }
    service.bridge.calendar = AsyncMock(return_value=[event])
    result = await service.refresh_webuntis("demo:1")
    assert result["entries"][0]["kind"] == "entfall"
    merged = service.substitutions(snapshot, snapshot["children"][0])
    assert len(merged) == 1 and merged[0]["additional_source"] == "webuntis"
    service.bridge.calendar.side_effect = ValueError("Unavailable")
    failed = await service.refresh_webuntis("demo:1")
    assert failed["entries"] == result["entries"] and failed["error"]


async def test_background_is_opt_in_and_does_not_send_by_default(demo_service):
    service = demo_service
    assert not service.settings.background_enabled and not service.settings.background_notifications
    service.bridge.send = AsyncMock()
    await service.background_tick()
    await service.background_tick()
    assert service.store.get("metadata", "poll:demo")
    assert service.bridge.send.await_count == 0


async def test_ha_ai_and_calendar_fixed_routes():
    bridge = Bridge(
        HomeAssistant(
            url="https://ha.example",
            ai_task_entity="ai_task.demo",
            webuntis_calendars={"demo:1": "calendar.demo"},
        )
    )
    bridge.request = AsyncMock(
        side_effect=[
            {"service_response": {"data": {"summary": "Hi"}}},
            {"service_response": {"calendar.demo": {"events": []}}},
        ]
    )
    assert await bridge.analyze("Prompt") == {"summary": "Hi"}
    assert (
        await bridge.calendar("demo:1", "2026-11-16T00:00:00+01:00", "2026-11-17T00:00:00+01:00")
        == []
    )
    paths = [c.args[1] for c in bridge.request.call_args_list]
    assert paths == [
        "/api/services/ai_task/generate_data?return_response",
        "/api/services/calendar/get_events?return_response",
    ]
    with pytest.raises(ValueError, match="mapped"):
        await bridge.calendar("demo:2", "start", "end")


async def test_new_item_and_substitution_alerts_are_quiet_on_import_and_deduplicated(live_service):
    service, backend = live_service
    await service.snapshot("testschool")
    assert service.store.get("metadata", "pending:testschool:1")["entries"] == []
    incoming = copy.deepcopy(backend.value["children"][0]["items"][1])
    incoming["id"] = "new-message"
    backend.value["children"][0]["items"].append(incoming)
    changed = copy.deepcopy(backend.value["children"][0]["substitutions"]["days"][0]["entries"][0])
    changed["lesson"] = "9"
    backend.value["children"][0]["substitutions"]["days"][0]["entries"].append(changed)
    service.last_attempt.clear()
    await service.snapshot("testschool", refresh=True)
    alerts = service.store.get("metadata", "pending:testschool:1")["entries"]
    assert {a["kind"] for a in alerts} == {"new_item", "substitution"}
    await service.snapshot("testschool")
    assert service.store.get("metadata", "pending:testschool:1")["entries"] == alerts


async def test_automatic_ai_queue_translation_retry_preserves_tasks(demo_service):
    service = demo_service
    await service.children()
    _, _, item = await service.item("demo:1", "demo-1-letter-1")
    raw = {
        "summary": "Museum bezahlen",
        "summaries": {"de": "Museum bezahlen"},
        "tasks": [{"title": "Museum bezahlen", "evidence": item["body"], "amount_cents": 1250}],
        "events": [],
    }
    service.bridge.analyze = AsyncMock(return_value=raw)
    await service.process_analysis_queue()
    assert service.store.get("analyses", item["id"])["method"] == "home_assistant"
    before = service.store.tasks()
    service.bridge.analyze = AsyncMock(return_value={"en": "Pay for the museum visit."})
    await service.process_analysis_queue()
    assert service.store.get("analyses", item["id"])["result"]["summaries"]["en"]
    assert service.store.tasks() == before
    service.settings = service.settings.model_copy(update={"summary_languages": ["de", "en", "es"]})
    service.bridge.analyze = AsyncMock(side_effect=ValueError("Not available"))
    await service.process_analysis_queue()
    retry = service.store.get("metadata", "analysis_retry:" + item["id"])
    assert retry["attempts"] == 1 and retry["next_attempt"]
    await service.process_analysis_queue()
    assert service.store.get("metadata", "analysis_retry:" + item["id"]) == retry
    # The queue budget can leave a different item for the next tick; it may run
    # once. No item already on the six-hour retry delay may run again.
    count = service.bridge.analyze.await_count
    await service.process_analysis_queue()
    assert service.bridge.analyze.await_count == count


async def test_bridge_http_does_not_redirect_or_leak_token(monkeypatch):
    from test_transport import FakeResponse

    captured = []
    monkeypatch.setenv("HA_TEST_TOKEN", "synthetic-secret-token")

    class FakeSession:
        def __init__(self, **kwargs):
            assert kwargs["timeout"].total == 90

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def request(self, method, url, **kwargs):
            captured.append((url, kwargs))
            return FakeResponse(b"{}", status=302, headers={"Location": "https://evil.invalid"})

    monkeypatch.setattr("elternportal_mcp.bridge.aiohttp.ClientSession", FakeSession)
    bridge = Bridge(HomeAssistant(url="https://ha.example", token_env="HA_TEST_TOKEN"))
    with pytest.raises(ValueError) as error:
        await bridge.request("POST", "/api/services/notify/demo", {"message": "Test"})
    assert "synthetic-secret-token" not in str(error.value)
    assert len(captured) == 1 and captured[0][1]["allow_redirects"] is False


def test_worker_lease_and_quiet_hours(demo_service, tmp_path):
    from datetime import UTC, timedelta

    from elternportal_mcp.storage import Store

    other = Store(tmp_path)
    expiry = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
    assert demo_service.store.claim_worker("one", expiry)
    assert not other.claim_worker("two", expiry)
    other.release_worker("two")
    assert not other.claim_worker("two", expiry)
    demo_service.store.release_worker("one")
    assert other.claim_worker("two", expiry)
    other.close()
    assert not demo_service.voice_allowed(datetime(2026, 11, 16, 6, 45))
    assert demo_service.voice_allowed(datetime(2026, 11, 16, 18, 30))


async def test_websocket_authentication_and_mobile_event(monkeypatch):
    sent, captured = [], []
    monkeypatch.setenv("HA_TEST_TOKEN", "synthetic-websocket-token")

    class WebSocket:
        closed = False
        messages = [
            {"type": "auth_required"},
            {"type": "auth_ok"},
            {"type": "result", "success": True},
            {"type": "event", "event": {"data": {"action": "ELTERNPORTAL_DONE:synthetic-task"}}},
        ]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            self.closed = True

        async def receive_json(self, **kwargs):
            return self.messages.pop(0)

        async def send_json(self, data):
            sent.append(data)

    class Session:
        def __init__(self, **kwargs):
            captured.append(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def ws_connect(self, url, **kwargs):
            assert url == "wss://ha.example/api/websocket"
            return WebSocket()

    monkeypatch.setattr("elternportal_mcp.bridge.aiohttp.ClientSession", Session)
    bridge = Bridge(HomeAssistant(url="https://ha.example", token_env="HA_TEST_TOKEN"))
    events = bridge.mobile_events()
    event = await anext(events)
    assert event["action"] == "ELTERNPORTAL_DONE:synthetic-task"
    assert sent == [
        {"type": "auth", "access_token": "synthetic-websocket-token"},
        {"id": 1, "type": "subscribe_events", "event_type": "mobile_app_notification_action"},
    ]
    await events.aclose()
    redirect_hook = captured[0]["trace_configs"][0].on_request_redirect[0]
    with pytest.raises(ValueError, match="redirect blocked"):
        await redirect_hook(None, None, None)


async def test_worker_cancellation_releases_shared_lease(demo_service, monkeypatch):
    import asyncio

    service = demo_service
    service.background_tick = AsyncMock()

    async def cancel(_seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr("elternportal_mcp.organizer.asyncio.sleep", cancel)
    with pytest.raises(asyncio.CancelledError):
        await service.background_loop()
    assert service.background_tick.await_count == 1
    assert service.store.get("metadata", "worker_lease") is None


async def test_non_pdf_attachment_is_saved_privately_without_execution(live_service):
    from pathlib import Path

    service, backend = live_service
    backend.pdf = b"\x89PNG\r\n\x1a\nsynthetic-image"
    backend.value["children"][0]["items"][0]["attachments"] = [
        {"name": "../../outside.png", "href": "/file"}
    ]
    result = await create_server(service).call_tool(
        "download_attachment",
        {
            "child_id": "testschool:1",
            "item_id": "demo-1-letter-1",
            "attachment_index": 0,
            "confirm_possible_receipt": True,
        },
    )
    structured = result[1]
    path = Path(structured["path"])
    assert path.is_relative_to(service.settings.data_dir) and path.suffix == ".png"
    assert await asyncio.to_thread(path.read_bytes) == backend.pdf
    assert backend.downloads == 1
    assert structured["receipt_may_have_been_confirmed"]
