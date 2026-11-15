"""Synthetic current data: no account, network or real children's information."""

from datetime import date, timedelta

from .storage import now


def snapshot() -> dict:
    today = date.today()
    children = []
    for number, name, classname in [("1", "Alex Beispiel", "6A"), ("2", "Robin Beispiel", "8B")]:
        child_id = f"demo:{number}"
        children.append(
            {
                "id": child_id,
                "school": "demo",
                "student_id": number,
                "name": name,
                "class_name": classname,
                "sections": {
                    s: {"status": "ok", "fetched_at": now()}
                    for s in (
                        "letter",
                        "message",
                        "blackboard",
                        "poll",
                        "appointment",
                        "lesson",
                        "substitution",
                        "sicknote",
                        "register",
                    )
                },
                "items": [
                    {
                        "id": f"demo-{number}-letter-1",
                        "child_id": child_id,
                        "kind": "letter",
                        "title": "Ausflug ins Museum",
                        "body": "Bitte bis Freitag 12,50 Euro überweisen und eine Trinkflasche mitbringen.",
                        "sent": today.isoformat(),
                        "url": "https://demo.eltern-portal.org/aktuelles/elternbriefe",
                        "sender": None,
                        "version": "demo-v1",
                        "attachments": [],
                        "meta": {"empfang_bestaetigt": False, "nummer": "1"},
                    },
                    {
                        "id": f"demo-{number}-message-1",
                        "child_id": child_id,
                        "kind": "message",
                        "title": "Material für Kunst",
                        "body": "Bitte am Montag Wasserfarben mitbringen.",
                        "sent": today.isoformat(),
                        "url": "https://demo.eltern-portal.org/meldungen/kommunikation_fachlehrer",
                        "sender": "Demo Lehrkraft",
                        "version": "demo-v1",
                        "attachments": [],
                        "meta": {},
                    },
                ],
                "appointments": [
                    {
                        "uid": f"demo-{number}-appointment-1",
                        "title": "SA Mathematik",
                        "kind": "schulaufgabe",
                        "start": (today + timedelta(days=2)).isoformat(),
                        "end": (today + timedelta(days=2)).isoformat(),
                    }
                ],
                "timetable": [
                    {
                        "weekday": 1,
                        "lesson": "1",
                        "start": "08:00",
                        "end": "08:45",
                        "subject": "M",
                        "room": "101",
                        "teacher": "Demo Lehrkraft",
                    }
                ],
                "substitutions": {
                    "available": True,
                    "stand": now(),
                    "days": [
                        {
                            "date": today.isoformat(),
                            "entries": [
                                {
                                    "lesson": "3",
                                    "teacher": "DE",
                                    "substitute": "---",
                                    "subject": "E",
                                    "old_subject": None,
                                    "room": "",
                                    "info": "Entfall",
                                    "kind": "entfall",
                                }
                            ],
                        }
                    ],
                },
                "sicknotes": [],
                "register": [
                    {
                        "subject": "Kunst",
                        "teacher": "Demo Lehrkraft",
                        "lesson": "1",
                        "rtype": "homework",
                        "start": today.isoformat(),
                        "completion": (today + timedelta(days=1)).isoformat(),
                        "body": "Wasserfarben mitbringen",
                    }
                ],
            }
        )
    return {
        "school": "demo",
        "school_name": "Demo-Gymnasium",
        "fetched_at": now(),
        "children": children,
        "teachers": {"DE": "Demo Lehrkraft"},
        "teacher_status": {"status": "ok", "fetched_at": now()},
    }
