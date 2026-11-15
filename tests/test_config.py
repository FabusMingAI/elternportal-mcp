import json

import pytest
from pydantic import ValidationError

from elternportal_mcp.config import School, Settings, load_settings


@pytest.mark.parametrize(
    "value",
    [
        "https://evil.org",
        "http://test.eltern-portal.org",
        "../test",
        "https://test.eltern-portal.org.evil.org",
        "https://u:p@test.eltern-portal.org",
        "https://test.eltern-portal.org:8443",
        "a/b",
        "",
        "a\nother",
    ],
)
def test_reject_untrusted_school_hosts(value):
    with pytest.raises(ValidationError):
        School(school=value)


def test_school_url_and_environment_are_explicit(monkeypatch):
    monkeypatch.setenv("USER", "operating-system-user")
    monkeypatch.setenv("MY_SCHOOL_PASSWORD", "secret-test-value")
    school = School(
        school="https://TEST.eltern-portal.org/path?username=ignored",
        username="parent@example.invalid",
        password_env="MY_SCHOOL_PASSWORD",
    )
    assert school.school == "test"
    assert school.username == "parent@example.invalid"
    assert school.password().get_secret_value() == "secret-test-value"
    assert "secret-test-value" not in repr(school.password())
    with pytest.raises(ValueError, match="Credentials missing"):
        School(school="test", username="parent@example.invalid").password()


def test_config_demo_and_duplicates(tmp_path):
    with pytest.raises(ValidationError):
        Settings(schools=[School(school="test"), School(school="test")])
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"schools": [{"school": "demo"}], "data_dir": str(tmp_path)}))
    assert load_settings(path).schools[0].school == "demo"
    assert not load_settings(path).allow_pdf_downloads
