import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CreateMessageResult, TextContent


async def test_new_features_through_stdio_and_real_sampling_callback(tmp_path):
    evidence = "Bitte bis Freitag 12,50 Euro überweisen und eine Trinkflasche mitbringen."
    requests = []

    async def sampling(_context, params):
        requests.append(params)
        if "Translate this" in params.messages[0].content.text:
            raw = {"en": "Pay for the museum visit."}
        else:
            raw = {
                "summary": "Museum bezahlen",
                "summaries": {"de": "Museum bezahlen"},
                "tasks": [
                    {
                        "title": "Museum bezahlen",
                        "type": "payment",
                        "amount_cents": 1250,
                        "due": "2026-11-20",
                        "evidence": evidence,
                    }
                ],
                "events": [{"title": "Museum", "date": "2026-11-20", "evidence": evidence}],
            }
        return CreateMessageResult(
            role="assistant",
            content=TextContent(type="text", text=json.dumps(raw)),
            model="synthetic-test-model",
        )

    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "elternportal_mcp", "--demo"],
        env={**os.environ, "ELTERNPORTAL_DEMO_DATA_DIR": str(tmp_path)},
    )
    async with (
        stdio_client(parameters) as (read, write),
        ClientSession(read, write, sampling_callback=sampling) as session,
    ):
        await session.initialize()
        child = {"child_id": "demo:1"}
        item = {**child, "item_id": "demo-1-letter-1"}
        await session.call_tool("list_children")
        analyzed = await session.call_tool(
            "analyze_item", {**item, "method": "sampling", "apply_tasks": True}
        )
        assert not analyzed.isError, analyzed
        assert analyzed.structuredContent["method"] == "sampling"
        translated = await session.call_tool("translate_summary", {**item, "languages": ["en"]})
        assert translated.structuredContent["summaries"]["en"] == "Pay for the museum visit."
        assert all(r.includeContext == "none" for r in requests)
        for name, args in [
            ("get_analysis", item),
            ("get_calendar", child),
            ("get_daily_plan", child),
            ("get_statistics", child),
            ("get_family_overview", {}),
            ("get_digest", {}),
            ("get_reminders", {}),
            ("get_changes", child),
            ("acknowledge_changes", {**child, "change_ids": []}),
            ("get_saved_attachment", item),
            ("mark_items_read", item),
            ("archive_item", item),
            ("list_archive", child),
        ]:
            result = await session.call_tool(name, args)
            assert not result.isError, (name, result)
        calendar = (await session.call_tool("get_calendar", child)).structuredContent["entries"]
        event_id = calendar[0]["id"]
        assert not (
            await session.call_tool("export_event", {**child, "event_id": event_id})
        ).isError
        assert not (
            await session.call_tool("archive_event", {**child, "event_id": event_id})
        ).isError
        invalid = await session.call_tool(
            "save_analysis",
            {
                **item,
                "analysis": {"tasks": [{"title": "Invented", "evidence": "Not in the source"}]},
            },
        )
        assert invalid.isError
        assert (await session.call_tool("send_briefing", {"confirm_send": False})).isError
        assert (await session.call_tool("refresh_webuntis", child)).isError
        assert (
            await session.call_tool("download_attachment", {**item, "attachment_index": 0})
        ).isError
