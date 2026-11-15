# Optionale HA-Brücke und Hintergrundbetrieb

Ohne HA funktionieren alle lokalen Organisationswerkzeuge. Für Push, Sprache,
WebUntis und den vorhandenen HA-KI-Anbieter kann eine Brücke eingerichtet werden.
Die Beispiele müssen lokal angepasst werden; das Repository enthält keine echten Zugangsdaten.

## Beispiel

Die folgenden Felder ergänzen die bestehende private Konfiguration:

```json
{
  "background_enabled": true,
  "background_notifications": false,
  "background_voice": false,
  "auto_ai_analysis": false,
  "scan_interval_seconds": 1800,
  "reminder_days": [3, 1, 0],
  "reminder_time": "18:30",
  "digest_time": "06:45",
  "timezone": "Europe/Berlin",
  "voice_start_time": "07:00",
  "voice_end_time": "20:00",
  "summary_languages": ["de", "en", "es", "ca"],
  "teacher_names": "both",
  "appointment_kinds": ["schulaufgabe", "test"],
  "own_class_only": true,
  "store_original_attachments": true,
  "home_assistant": {
    "url": "https://ha.example.invalid",
    "token_env": "HOME_ASSISTANT_TOKEN",
    "notify_services": ["notify.mobile_app_example"],
    "tts_entity": "tts.example",
    "media_players": ["media_player.example"],
    "ai_task_entity": "ai_task.example",
    "webuntis_calendars": {
      "myschool:CHILD_ID_FROM_LIST_CHILDREN": "calendar.example"
    }
  }
}
```

Nur tatsächlich benötigte HA-Felder setzen. `url` bezeichnet ausschließlich den
Ursprung ohne Pfad oder Zugangsdaten. Den langlebigen HA-Zugriffstoken über die
benannte Umgebungsvariable an den Server übergeben. Für unverschlüsseltes HTTP
im bewusst vertrauten lokalen Netz ist zusätzlich `allow_local_http=true` im
HA-Block erforderlich. HTTPS bleibt der Standard; TLS-Prüfung bleibt aktiv.
Der Token wird nicht in Werkzeugargumenten oder der lokalen Datenbank gespeichert.

Die Brücke ruft nur feste Funktionen auf: konfigurierte Kalender lesen,
`ai_task.generate_data`, konfigurierte `notify.*`-Dienste, `tts.speak` und
HA-Companion-Aktionsereignisse. Das MCP-Werkzeug erlaubt keine frei wählbaren
HA-Serviceaufrufe. Fehlerantworten enthalten keine Tokens oder Portal-HTML.

## Erinnerungen und Sprache

`get_reminders` und `get_digest` zeigen eine Vorschau ohne Versand. Für den
bewusst gewünschten Versand `send_briefing(confirm_send=true)` verwenden;
`speak=true` wählt die konfigurierten Lautsprecher. Jede Mitteilung kann
persönliche Informationen enthalten.

Für selbständige Zustellung `background_notifications=true` lokal setzen.
Zusätzlich aktiviert `background_voice=true` gesprochene Zusammenfassungen
innerhalb des Zeitfensters. Lokale Freigaben gelten als dauerhafte Zustimmung
für diesen konfigurierten Dienst; nicht aktivieren, wenn dies nicht gewünscht ist.

Gleiche tägliche Zusammenfassungen werden nicht erneut gesendet; bei teilweise
fehlgeschlagener Push-Zustellung werden bereits erreichte Ziele übersprungen.
Bei Netzwerkabbrüchen nach einem tatsächlich erfolgten Versand kann trotzdem
eine Wiederholung entstehen: eine externe Zustellung ist nicht atomar mit SQLite.

Push-Erinnerungen enthalten „Erledigt“ und „Morgen erinnern“. Ihre Rückmeldung
wird über den authentifizierten HA-WebSocket verarbeitet. Dazu muss der
Hintergrundprozess laufen. Die Aktionen ändern nur lokale MCP-Aufgaben.

## KI und Übersetzungen

Standardmäßig laufen lokale Regeln. Vorschläge sind prüfbedürftig und zitieren
den erkannten Quelltext. Die Regeln erkennen keine beliebigen natürlichen
Zeitangaben zuverlässig und ersetzen keine Prüfung des Originalbriefs.

`analyze_item` kann ausdrücklich MCP-Sampling oder den konfigurierten HA-KI-Dienst
nutzen. Damit werden Quelltexte an dessen Modellanbieter übertragen. Mit
`auto_ai_analysis=true` und laufendem Hintergrundprozess geschieht dies auch
automatisch für anstehende Auswertungen und fehlende gewählte Übersetzungen.
Der Server lädt dafür niemals eigenständig PDFs herunter.

Fehlgeschlagene automatische Analysen/Übersetzungen werden nach sechs Stunden
erneut versucht, maximal dreimal. `get_health` zeigt die anstehenden Auswertungen
und Übersetzungen. Bereits bearbeitete Aufgaben/Kommentare bleiben erhalten;
Übersetzungen verändern nur Zusammenfassungen.

## WebUntis

Den Kalender der separaten HA-WebUntis-Integration pro Kind zuordnen und dort
JSON-Beschreibungen sowie ausgefallene Stunden aktivieren. Es werden unterstützte
Änderungen für die nächsten 14 Tage gelesen, kein zweiter vollständiger Stundenplan.
Bei Quellenfehlern bleiben frühere Ergebnisse mit Fehlerkennzeichnung erhalten.
Fehlende Lehrerfelder sind kein Beleg für Unterrichtsausfall. Nicht eindeutig
erkennbare Verschiebungen/zusätzliche Stunden bleiben wie in der HA-Version begrenzt.

## Laufzeit und Dateien

Ein MCP-Prozess kann Hintergrundjobs nur ausführen, solange der Client ihn
laufen lässt. Für vom Chat unabhängigen Betrieb:

```bash
elternportal-mcp --config /absolute/path/private/config.json --worker
```

Die Konfiguration muss `background_enabled=true` enthalten. Den Prozess über
einen eigenen Dienstmanager dauerhaft starten, falls gewünscht. Das passiert
nicht durch die Installation. Ein Worker-Lease verhindert doppelte geplante
Jobs bei mehreren Prozessen mit demselben Datenverzeichnis. Nach einem harten
Abbruch kann die Freigabe bis zu zehn Minuten dauern.

Mitteilungen und Zustände aus 0.1.0 werden beim Start übernommen; SQLite ergänzt
die neuen Tabellen. Originalanhänge werden erst bei ausdrücklich freigegebenen
Downloads gespeichert. Sie liegen im privaten Datenverzeichnis unter
`attachments/Schule/Kind-Hash/Schuljahr/Inhalts-Hash`. Der Server öffnet oder
führt sie nicht aus. `get_saved_attachment` liefert nur lokale Metadaten.

Quellen: [HA REST API](https://contributors.home-assistant.io/core/internals/rest-api/),
[HA AI Task](https://www.home-assistant.io/integrations/ai_task/),
[HA Calendar](https://www.home-assistant.io/integrations/calendar/).
