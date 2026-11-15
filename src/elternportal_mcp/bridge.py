"""Optional, explicitly configured Home Assistant REST adapter."""

from __future__ import annotations

import json
import os

import aiohttp

from .config import HomeAssistant


class Bridge:
    def __init__(self, config: HomeAssistant | None):
        self.config = config

    async def request(self, method: str, path: str, data: dict | None = None):
        config = self.config
        if config is None:
            raise ValueError("Home Assistant bridge not configured")
        token = os.environ.get(config.token_env)
        if not token:
            raise ValueError("Home Assistant token is missing")
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90)) as session:
                async with session.request(
                    method,
                    config.url.rstrip("/") + path,
                    headers={"Authorization": "Bearer " + token},
                    json=data,
                    allow_redirects=False,
                ) as response:
                    if response.status != 200:
                        raise ValueError("Home Assistant request failed; check local configuration")
                    result = bytearray()
                    async for chunk in response.content.iter_chunked(65536):
                        result.extend(chunk)
                        if len(result) > 4 * 1024**2:
                            raise ValueError("Home Assistant response too large")
                    return json.loads(result)
        except (aiohttp.ClientError, TimeoutError, json.JSONDecodeError):
            raise ValueError("Home Assistant connection or response failed") from None

    async def calendar(self, child_id: str, start: str, end: str) -> list[dict]:
        config = self.config
        entity = config.webuntis_calendars.get(child_id) if config else None
        if entity is None:
            raise ValueError("No WebUntis calendar mapped for this child")
        response = await self.request(
            "POST",
            "/api/services/calendar/get_events?return_response",
            {"entity_id": entity, "start_date_time": start, "end_date_time": end},
        )
        return response["service_response"][entity]["events"]

    async def analyze(self, instructions: str) -> dict:
        if not self.config or not self.config.ai_task_entity:
            raise ValueError("Home Assistant AI Task entity not configured")
        result = await self.request(
            "POST",
            "/api/services/ai_task/generate_data?return_response",
            {
                "entity_id": self.config.ai_task_entity,
                "task_name": "Eltern-Portal MCP analysis",
                "instructions": instructions,
            },
        )
        data = result.get("service_response", {}).get("data")
        if not isinstance(data, (str, dict)):
            raise ValueError("Home Assistant AI returned an unsupported response")
        return data

    async def send(
        self,
        title: str,
        message: str,
        *,
        speak: bool = False,
        skip: set[str] | None = None,
        actions: list[dict] | None = None,
    ) -> dict:
        if not self.config:
            raise ValueError("Home Assistant bridge not configured")
        delivered, errors = [], []
        targets = self.config.media_players if speak else self.config.notify_services
        if not targets or (speak and not self.config.tts_entity):
            raise ValueError(
                "No configured voice targets" if speak else "No configured notification services"
            )
        for target in targets:
            if target in (skip or set()):
                delivered.append(target)
                continue
            try:
                if speak:
                    await self.request(
                        "POST",
                        "/api/services/tts/speak",
                        {
                            "entity_id": self.config.tts_entity,
                            "media_player_entity_id": target,
                            "message": message[:8000],
                            "cache": False,
                        },
                    )
                else:
                    await self.request(
                        "POST",
                        "/api/services/notify/" + target.split(".", 1)[1],
                        {
                            "title": title[:200],
                            "message": message[:8000],
                            **({"data": {"actions": actions}} if actions else {}),
                        },
                    )
                delivered.append(target)
            except ValueError:
                errors.append(target)
        return {"delivered": delivered, "failed": errors}

    async def mobile_events(self):
        config = self.config
        if config is None or not os.environ.get(config.token_env):
            raise ValueError("Home Assistant token is missing")
        url = (
            config.url.rstrip("/").replace("https://", "wss://", 1).replace("http://", "ws://", 1)
            + "/api/websocket"
        )
        trace = aiohttp.TraceConfig()

        async def reject_redirect(*_args):
            raise ValueError("Home Assistant websocket redirect blocked")

        trace.on_request_redirect.append(reject_redirect)
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=None, connect=15), trace_configs=[trace]
        ) as session:
            async with session.ws_connect(url, heartbeat=30, max_msg_size=4 * 1024**2) as websocket:
                if (await websocket.receive_json(timeout=15)).get("type") != "auth_required":
                    raise ValueError("Unexpected HA websocket handshake")
                await websocket.send_json(
                    {"type": "auth", "access_token": os.environ[config.token_env]}
                )
                if (await websocket.receive_json(timeout=15)).get("type") != "auth_ok":
                    raise ValueError("Home Assistant authentication failed")
                await websocket.send_json(
                    {
                        "id": 1,
                        "type": "subscribe_events",
                        "event_type": "mobile_app_notification_action",
                    }
                )
                while not websocket.closed:
                    message = await websocket.receive_json()
                    if message.get("type") == "event":
                        yield message.get("event", {}).get("data", {})
