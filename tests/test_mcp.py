import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_real_stdio_tools_resources_prompts_and_persistent_tasks(tmp_path):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "elternportal_mcp", "--demo"],
        env={**os.environ, "ELTERNPORTAL_DEMO_DATA_DIR": str(tmp_path)},
    )
    task_id = None
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = (await session.list_tools()).tools
        assert len(tools) == 20
        by_name = {t.name: t for t in tools}
        assert by_name["download_pdf"].annotations.readOnlyHint is False
        assert by_name["get_item"].annotations.readOnlyHint is True
        children = await session.call_tool("list_children")
        assert children.structuredContent["children"][0]["id"] == "demo:1"
        for name, arguments in [
            ("get_health", {}),
            ("list_schools", {}),
            ("refresh_school", {"school": "demo"}),
            ("get_capabilities", {"child_id": "demo:1"}),
            ("list_items", {"child_id": "demo:1", "query": "Museum"}),
            ("get_item", {"child_id": "demo:1", "item_id": "demo-1-letter-1"}),
            ("get_timetable", {"child_id": "demo:1"}),
            ("get_substitutions", {"child_id": "demo:1"}),
            ("get_appointments", {"child_id": "demo:1"}),
            ("get_sick_notes", {"child_id": "demo:1"}),
            ("get_class_register", {"child_id": "demo:1"}),
            ("get_teachers", {"school": "demo"}),
            ("get_cached_document", {"child_id": "demo:1", "item_id": "demo-1-letter-1"}),
            (
                "set_item_status",
                {"child_id": "demo:1", "item_id": "demo-1-letter-1", "status": "in_progress"},
            ),
            ("get_overview", {"child_id": "demo:1"}),
        ]:
            result = await session.call_tool(name, arguments)
            assert not result.isError, (name, result)
            assert result.structuredContent is not None
        created = await session.call_tool(
            "add_task",
            {
                "child_id": "demo:1",
                "title": "Museum bezahlen",
                "amount_cents": 1250,
                "source_item_id": "demo-1-letter-1",
            },
        )
        assert not created.isError
        task_id = created.structuredContent["id"]
        changed = await session.call_tool("update_task", {"task_id": task_id, "status": "done"})
        assert changed.structuredContent["status"] == "done"
        assert (await session.call_tool("list_tasks", {"status": "done"})).structuredContent[
            "total"
        ] == 1
        rejected = await session.call_tool(
            "download_pdf",
            {"child_id": "demo:1", "item_id": "demo-1-letter-1", "attachment_index": 0},
        )
        assert rejected.isError
        invalid = await session.call_tool("list_items", {"child_id": "demo:1", "limit": 101})
        assert invalid.isError
        assert (await session.read_resource("elternportal://guide")).contents
        assert len((await session.list_prompts()).prompts) == 2
        assert (await session.get_prompt("school_briefing", {"child_id": "demo:1"})).messages
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        rows = (await session.call_tool("list_tasks")).structuredContent["entries"]
        assert rows[0]["id"] == task_id and rows[0]["status"] == "done"
