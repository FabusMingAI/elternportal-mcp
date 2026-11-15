import pytest

from elternportal_mcp.vendor.parsers import (
    clean_appointment_title,
    parse_substitutions,
    parse_teachers,
    parse_timetable,
)


@pytest.mark.parametrize("with_subject", [True, False])
def test_five_and_six_column_substitutions(with_subject):
    subject_header = "<td>Fach</td>" if with_subject else ""
    subject = (
        '<td><span style="text-decoration: line-through;">M</span> E</td>' if with_subject else ""
    )
    html = f"""<div id="asam_content"><div class="main_center">
      <div class="list">Mo., 16.11.2026</div><table>
      <tr class="vp_plan_head"><td>Std.</td><td>Betrifft.</td><td>Vertretung</td>{subject_header}<td>Raum</td><td>Info</td></tr>
      <tr><td>3.</td><td>DE</td><td>AB</td>{subject}<td>A101</td><td>Vertretung</td></tr>
      </table><div>Stand: 15.11.2026 08:00</div></div></div>"""
    result = parse_substitutions(html)
    entry = result["days"][0]["entries"][0]
    assert entry["room"] == "A101" and entry["teacher"] == "DE"
    assert entry["subject"] == ("E" if with_subject else "")
    assert entry["old_subject"] == ("M" if with_subject else None)
    assert entry["lesson"] == "3" and entry["kind"] == "vertretung"


def test_unavailable_is_different_from_explicit_empty_plan():
    assert not parse_substitutions("<html>Login</html>")["available"]
    result = parse_substitutions(
        '<div id="asam_content"><div class="main_center"><div class="list">16.11.2026</div><table><tr><td>Keine Vertretungen</td></tr></table></div></div>'
    )
    assert result["available"] and result["days"][0]["entries"] == []


def test_timetable_retains_times_and_rooms():
    html = '<div id="asam_content"><div class="table-responsive"><table><tr><td>1.<br>8:00 - 8:45</td><td>M<br>A101</td><td>E<br>B102</td><td></td><td></td><td></td></tr></table></div></div>'
    result = parse_timetable(html)
    assert result[0] == {
        "weekday": 1,
        "lesson": "1",
        "start": "08:00",
        "end": "08:45",
        "subject": "M",
        "room": "A101",
    }
    assert result[1]["weekday"] == 2


def test_teacher_list_and_calendar_title():
    assert parse_teachers(
        "<h2>Stundenplankürzel der Lehrkräfte</h2><table><tr><td>DE</td><td>Demo Teacher</td></tr></table>"
    ) == {"DE": "Demo Teacher"}
    assert clean_appointment_title("14:00 - 16:00<br />5: Lernwerkstatt") == (
        "5: Lernwerkstatt",
        "14:00",
        "16:00",
    )
