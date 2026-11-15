import copy
import sqlite3
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from elternportal_mcp.analysis import rules, verify
from elternportal_mcp.server import create_server
from elternportal_mcp.storage import Store


def analysis(item, **overrides):
    return {
        "summary": "Ausflug bezahlen",
        "summaries": {"de": "Ausflug bezahlen"},
        "tasks": [
            {
                "title": "Museum bezahlen",
                "type": "payment",
                "amount_cents": 1250,
                "due": "2026-11-20",
                "evidence": item["body"],
            }
        ],
        "events": [],
        **overrides,
    }


def test_rule_deadlines_amounts_and_evidence():
    text = "Bitte bis zum 12.01.2027 überweisen: 1.250,50 Euro.\nEmpfänger: Förderverein\nIBAN: DE89 3704 0044 0532 0130 00\nVerwendungszweck: Museum Alex"
    result = rules("Museum", text, date(2026, 12, 20))
    task = result.tasks[0]
    assert task.amount_cents == 125050 and task.due == "2027-01-12"
    assert task.iban == "DE89370400440532013000"
    assert task.payee == "Förderverein" and task.reference == "Museum Alex"
    assert verify(result.model_dump(), "Museum\n" + text).tasks
    assert not rules(
        "Info", "Der Bus kostet 100 Euro. Die Schule bezahlt alles.", date.today()
    ).tasks
    assert not rules("Klasse 9B", "Bitte 10 Euro überweisen.", date.today(), "6A").tasks


def test_rules_avoid_invalid_dates_and_infer_school_year():
    result = rules(
        "Anmeldung",
        "Bitte bis 31.02.2026 anmelden. Rückgabe: 12.01. unterschrieben.",
        date(2026, 12, 20),
    )
    assert result.tasks[0].due == "2027-01-12"
    assert rules("Info", "Bitte 999999999999999999999 Euro überweisen.", date.today()).tasks == []


async def test_auto_tasks_receipts_polls_and_idempotency(live_service, monkeypatch):
    service, backend = live_service
    item = copy.deepcopy(backend.value["children"][0]["items"][0])
    item.update(
        id="poll-one", kind="poll", body="", meta={"ende": "2099-12-31", "abgestimmt": None}
    )
    backend.value["children"][0]["items"].append(item)
    await service.snapshot("testschool")
    before = service.store.tasks("testschool:1")
    assert any(t.get("type") == "receipt" for t in before)
    assert any(t.get("type") == "poll" for t in before)
    assert any(t.get("amount_cents") == 1250 for t in before)
    monkeypatch.setattr("elternportal_mcp.organizer.now", lambda: "2099-12-31T23:59:59+00:00")
    await service.snapshot("testschool")
    assert service.store.tasks("testschool:1") == before
    backend.value["children"][0]["items"][0]["meta"]["empfang_bestaetigt"] = True
    backend.value["children"][0]["items"][-1]["meta"]["abgestimmt"] = "2026-11-15"
    service.last_attempt.clear()
    await service.snapshot("testschool", refresh=True)
    portal = [t for t in service.store.tasks("testschool:1") if t.get("origin") == "portal"]
    assert all(t["status"] == "done" for t in portal)
    assert backend.downloads == 0


async def test_changed_content_unreads_but_whitespace_does_not(live_service):
    service, backend = live_service
    await service.snapshot("testschool")
    await service.mark_read("testschool:1", "demo-1-letter-1", True)
    backend.value["children"][0]["items"][0]["body"] += "  \n "
    service.last_attempt.clear()
    await service.snapshot("testschool", refresh=True)
    assert service.store.get("item_states", "demo-1-letter-1")["read"]
    backend.value["children"][0]["items"][0]["body"] += " Neu: Abfahrt 8 Uhr."
    service.last_attempt.clear()
    await service.snapshot("testschool", refresh=True)
    assert not service.store.get("item_states", "demo-1-letter-1")["read"]
    assert len(service.store.get("history", "demo-1-letter-1")["changes"]) == 1
    pending = service.store.get("metadata", "pending:testschool:1")["entries"]
    assert any(e["kind"] == "changed_item" for e in pending)


async def test_analysis_quote_validation_and_user_edits(demo_service):
    service = demo_service
    _, _, item = await service.item("demo:1", "demo-1-letter-1")
    bad = analysis(item)
    bad["tasks"][0]["evidence"] = "An invented quote"
    with pytest.raises(ValueError, match="quote evidence"):
        service.save_analysis(item, bad, method="client", apply=True)
    good = analysis(item)
    row = service.save_analysis(item, good, method="client", apply=True)
    task = next(
        t
        for t in service.store.tasks("demo:1")
        if t.get("source_hash") == row["content_hash"] and t.get("amount_cents") == 1250
    )
    task.update(title="My edited task", status="done", user_modified=True)
    service.store.put("tasks", task["id"], task)
    service.save_analysis(item, good, method="client", apply=True)
    assert service.store.get("tasks", task["id"])["title"] == "My edited task"
    assert service.store.get("tasks", task["id"])["status"] == "done"
    assert service.store.get("analyses", item["id"])["result"]["summaries"]["de"]


async def test_archived_and_removed_items_retain_details(live_service):
    service, backend = live_service
    await service.snapshot("testschool")
    mcp = create_server(service)
    await mcp.call_tool("archive_item", {"child_id": "testschool:1", "item_id": "demo-1-letter-1"})
    assert (await service.items("testschool:1", kind="letter"))["total"] == 0
    backend.value["children"][0]["items"] = []
    service.last_attempt.clear()
    await service.snapshot("testschool", refresh=True)
    assert (await service.get_item("testschool:1", "demo-1-letter-1"))["item"]["body"]
    assert (await service.items("testschool:1", include_archived=True))["total"] == 2
    assert service.store.tasks("testschool:1")


async def test_calendar_archive_does_not_complete_tasks_and_ics(demo_service):
    service = demo_service
    await service.children()
    task = service.store.add_task("demo:1", "Frist, mit Übung", due="2026-11-20")
    event_id = "task:" + task["id"]
    exported = await service.calendar_export("demo:1", event_id)
    assert "DTSTART;VALUE=DATE:20261120" in exported["ics"]
    assert "DTEND;VALUE=DATE:20261121" in exported["ics"]
    assert "Frist\\, mit Übung" in exported["ics"]
    again = await service.calendar_export("demo:1", event_id)
    assert (
        exported["ics"].split("UID:")[1].split("\r\n")[0]
        == again["ics"].split("UID:")[1].split("\r\n")[0]
    )
    await create_server(service).call_tool(
        "archive_event", {"child_id": "demo:1", "event_id": event_id}
    )
    assert event_id not in {e["id"] for e in await service.events("demo:1")}
    assert service.store.get("tasks", task["id"])["status"] == "open"


async def test_timed_letter_event_and_teacher_names(demo_service):
    service = demo_service
    _, _, item = await service.item("demo:1", "demo-1-letter-1")
    row = analysis(
        item,
        tasks=[],
        events=[
            {
                "title": "Museum",
                "date": "2026-11-20",
                "time": "14:00",
                "end_time": "16:00",
                "evidence": item["body"],
                "location": "Museum",
            }
        ],
    )
    service.save_analysis(item, row, method="client", apply=True)
    event = next(e for e in await service.events("demo:1") if e["origin"] == "analysis")
    exported = await service.calendar_export("demo:1", event["id"])
    assert "DTSTART:20261120T130000Z" in exported["ics"]
    assert "DTEND:20261120T150000Z" in exported["ics"]
    assert "TRIGGER:-PT1H" in exported["ics"]
    # Previewing a different analysis must not replace already accepted events.
    service.save_analysis(item, analysis(item, tasks=[], events=[]), method="client", apply=False)
    assert event["id"] in {e["id"] for e in await service.events("demo:1")}


async def test_background_school_failure_does_not_starve_other_schools(demo_service):
    from unittest.mock import AsyncMock

    service = demo_service
    service.schools = {"broken": None, "working": None}

    async def refresh(code, **kwargs):
        if code == "broken":
            raise ValueError("Unavailable")
        return {}

    service.snapshot = AsyncMock(side_effect=refresh)
    await service.background_tick()
    assert service.store.get("metadata", "poll:broken")["error"]
    assert service.store.get("metadata", "poll:working")["error"] is None


async def test_reminders_snooze_and_school_year_statistics(live_service, monkeypatch):
    service, backend = live_service
    clock = datetime(2026, 11, 16, 18, 30, tzinfo=ZoneInfo("Europe/Berlin"))
    monkeypatch.setattr(service, "local_now", lambda: clock)
    backend.value["children"][0]["sicknotes"] = [
        {"start": "2026-11-12", "end": "2026-11-16"},
        {"start": "2026-11-13", "end": "2026-11-13"},
    ]
    await service.snapshot("testschool")
    task = service.store.add_task("testschool:1", "Overdue", due="2026-11-15")
    assert (await service.statistics("testschool:1"))["traffic_light"] == "red"
    assert (await service.statistics("testschool:1"))["sick_weekdays"] == 3
    assert (await service.reminders("testschool:1"))["total"] == 1
    await create_server(service).call_tool("snooze_task", {"task_id": task["id"]})
    assert (await service.reminders("testschool:1"))["total"] == 0
    assert service.store.get("tasks", task["id"])["due"] == "2026-11-15"


def test_v1_database_migration_keeps_existing_data(tmp_path):
    db = sqlite3.connect(tmp_path / "state.sqlite3")
    db.executescript(
        "CREATE TABLE tasks(id TEXT PRIMARY KEY,payload TEXT NOT NULL); PRAGMA user_version=1;"
    )
    db.execute(
        "INSERT INTO tasks VALUES (?,?)",
        ("old", '{"id":"old","title":"Keep me","child_id":"demo:1","created_at":"2026-01-01"}'),
    )
    db.commit()
    db.close()
    store = Store(tmp_path)
    assert store.get("tasks", "old")["title"] == "Keep me"
    assert store.db.execute("PRAGMA user_version").fetchone()[0] == 2
    assert store.records("analyses") == []
    store.close()
