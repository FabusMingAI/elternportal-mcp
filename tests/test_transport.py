import json

import pytest

from elternportal_mcp.portal import (
    AuthenticationRequired,
    PortalError,
    PortalHTTP,
    inspect_html,
    safe_url,
)


class Stream:
    def __init__(self, data):
        self.data = data

    async def iter_chunked(self, size):
        for pos in range(0, len(self.data), size):
            yield self.data[pos : pos + size]


class FakeResponse:
    def __init__(self, data=b"ok", status=200, headers=None, declared_length=None):
        self.status = status
        self.headers = headers or {}
        self.content = Stream(data)
        self.content_length = declared_length

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class Session:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


@pytest.mark.parametrize(
    "target",
    [
        "https://evil.org",
        "//evil.org",
        "http://test.eltern-portal.org",
        "https://test.eltern-portal.org:8888",
        "https://u:p@test.eltern-portal.org",
    ],
)
def test_blocks_cross_origin_and_plaintext(target):
    with pytest.raises(PortalError):
        safe_url("https://test.eltern-portal.org/", target)


async def test_never_follows_redirect_to_other_origin():
    session = Session(FakeResponse(status=307, headers={"Location": "https://evil.org"}))
    http = PortalHTTP(session, "https://test.eltern-portal.org/")
    with pytest.raises(PortalError, match="blocked"):
        async with http.post(http.base, data={"password": "secret"}):
            pass
    assert len(session.calls) == 1
    assert session.calls[0][2]["allow_redirects"] is False


async def test_login_redirect_is_detected_instead_of_empty_result():
    session = Session(
        FakeResponse(status=302, headers={"Location": "/"}),
        FakeResponse(b'<form class="form-signin"><input type="password"></form>'),
    )
    http = PortalHTTP(session, "https://test.eltern-portal.org/")
    http.authenticated = True
    with pytest.raises(AuthenticationRequired):
        async with http.get(http.base + "service/stundenplan"):
            pass


async def test_303_discards_login_payload():
    session = Session(FakeResponse(status=303, headers={"Location": "/"}), FakeResponse())
    http = PortalHTTP(session, "https://test.eltern-portal.org/")
    async with http.post(http.base, data={"password": "secret"}):
        pass
    assert session.calls[1] == ("GET", http.base, {"allow_redirects": False})


async def test_streamed_size_limit_without_content_length(monkeypatch):
    monkeypatch.setattr("elternportal_mcp.portal.MAX_PAGE_BYTES", 10)
    http = PortalHTTP(Session(FakeResponse(b"x" * 11)), "https://test.eltern-portal.org/")
    with pytest.raises(PortalError, match="too_large"):
        async with http.get(http.base):
            pass


async def test_json_with_wrong_mimetype_is_supported():
    http = PortalHTTP(
        Session(FakeResponse(b'{"success":1,"result":[]}', headers={"Content-Type": "text/html"})),
        "https://test.eltern-portal.org/",
    )
    http.authenticated = True
    async with http.get(http.base + "api/ws_get_termine.php") as response:
        assert await response.json() == {"success": 1, "result": []}


@pytest.mark.parametrize("status", [401, 403, 404, 500])
async def test_failed_http_never_parses_empty_success(status):
    http = PortalHTTP(Session(FakeResponse(status=status)), "https://test.eltern-portal.org/")
    with pytest.raises(PortalError):
        async with http.get(http.base):
            pass


def test_layout_change_is_explicit():
    with pytest.raises(PortalError, match="unrecognized"):
        inspect_html("/service/stundenplan", '<div id="asam_content">new layout</div>')


async def test_real_backend_parsers_and_child_switches(monkeypatch, tmp_path):
    import re
    from datetime import date
    from urllib.parse import parse_qs, urlsplit

    import pyelternportal.demo as fixtures
    from bs4 import BeautifulSoup

    from elternportal_mcp.config import School, Settings
    from elternportal_mcp.portal import PortalBackend

    routes = {
        "/": fixtures.DEMO_HTML_BASE,
        "/includes/project/auth/login.php": fixtures.DEMO_HTML_LOGIN,
        "/service/stundenplan": fixtures.DEMO_HTML_LESSON,
        "/service/vertretungsplan": fixtures.DEMO_HTML_SUBSTITUTION,
        "/aktuelles/elternbriefe": fixtures.DEMO_HTML_LETTER,
        "/aktuelles/schwarzes_brett": fixtures.DEMO_HTML_BLACKBOARD,
        "/aktuelles/umfragen": fixtures.DEMO_HTML_POLL,
        "/meldungen/kommunikation_fachlehrer": fixtures.DEMO_HTML_MESSAGE,
        "/meldungen/krankmeldung": fixtures.DEMO_HTML_SICKNOTE,
        "/service/klassenbuch": fixtures.DEMO_HTML_REGISTER,
        "/api/ws_get_termine.php": fixtures.DEMO_JSON_APPOINTMENT,
        "/api/set_child.php": '{"success":1}',
        "/logout": fixtures.DEMO_HTML_LOGOUT,
        "/service/schulinformationen": '<div id="asam_content"><h2>Stundenplankürzel der Lehrkräfte</h2><table><tr><td>DE</td><td>Demo Teacher</td></tr></table></div>',
    }
    routes["/includes/project/auth/login.php"] = routes["/includes/project/auth/login.php"].replace(
        "</select>", '<option value="2">Robin Beispiel (8b)</option></select>', 1
    )
    letter_page = BeautifulSoup(routes["/aktuelles/elternbriefe"], "html.parser")
    attachment = letter_page.select_one(".link_nachrichten")
    attachment.name = "a"
    attachment["href"] = "aktuelles/get_file/?repo=1&csrf=synthetic-fresh-token"
    routes["/aktuelles/elternbriefe"] = str(letter_page)
    selected = []
    downloads = []

    class FixtureSession:
        def __init__(self, **kwargs):
            assert kwargs["timeout"].total <= 120
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def request(self, method, url, **kwargs):
            path = urlsplit(url).path
            if "get_file" in path:
                downloads.append(url)
                return FakeResponse(b"%PDF-synthetic-fixture")
            if path == "/api/set_child.php":
                assert method == "POST"
                selected.append(parse_qs(urlsplit(url).query)["id"][0])
            if path.startswith("/meldungen/kommunikation_fachlehrer/"):
                html = fixtures.DEMO_HTML_MESSAGE_DETAIL
            elif path.startswith("/aktuelles/umfragen/"):
                html = fixtures.DEMO_HTML_POLL_DETAIL
            else:
                html = routes.get(path, '<div id="asam_content">Unknown fixture path</div>')
            html = re.sub(r"\d{2}\.\d{2}\.20\d{2}", date.today().strftime("%d.%m.%Y"), html)
            return FakeResponse(html.encode())

    monkeypatch.setenv("TEST_PASSWORD", "synthetic-password")
    monkeypatch.setattr("elternportal_mcp.portal.aiohttp.ClientSession", FixtureSession)
    school = School(
        school="fixture", username="parent@example.invalid", password_env="TEST_PASSWORD"
    )
    backend = PortalBackend(Settings(schools=[school], data_dir=tmp_path))
    result = await backend.fetch(school)
    assert len(result["children"]) >= 2
    assert selected == [c["student_id"] for c in result["children"]]
    assert len(set(selected)) == len(selected)
    for child in result["children"]:
        for section in ("letter", "message", "appointment", "lesson", "substitution"):
            assert child["sections"][section]["status"] == "ok", (section, child["sections"])
        assert child["timetable"]
        assert child["substitutions"]["available"]
    assert "synthetic-password" not in json.dumps(result)
    assert not downloads
    child = result["children"][1]
    letter = next(i for i in child["items"] if i["kind"] == "letter" and i["attachments"])
    # A stale or forged cache link must not be used: rediscover on the fresh page.
    letter["attachments"][0]["href"] = "https://evil.invalid/file"
    content = await backend.download(school, child, letter["id"], 0, "letter")
    assert content.startswith(b"%PDF-")
    assert selected[-1] == child["student_id"]
    assert len(downloads) == 1 and downloads[0].startswith("https://fixture.eltern-portal.org/")
    with pytest.raises(PortalError, match="attachment_not_found"):
        await backend.download(school, child, letter["id"], 99, "letter")
