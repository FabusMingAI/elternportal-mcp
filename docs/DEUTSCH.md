# Eltern-Portal MCP Bavaria – Anleitung

Dieser lokale MCP-Server verbindet einen KI-Assistenten mit dem Eltern-Portal
unter `SCHULE.eltern-portal.org`. Er baut auf unserer Home-Assistant-Integration
[Eltern Portal Manager Bavaria](https://github.com/FabusMingAI/ha-schulmanager)
und deren bewährten Parsern auf. Home Assistant wird dafür nicht benötigt.

**Erste Community-Version 0.1.0:** Demo, MCP-Protokoll und simulierte Portalabläufe
werden automatisch getestet. Dieser eigenständige MCP-Server ist noch nicht mit
einem echten Schulzugang geprüft. Funktionen hängen von den Freischaltungen der
Schule ab. Zwei-Faktor-Anmeldung wird noch nicht unterstützt.

## Funktionsumfang

- Mehrere Schulen und Kinder mit eindeutigen IDs.
- Elternbriefe, Lehrermitteilungen, Schwarzes Brett und Umfragen lesen und durchsuchen.
- Stundenplan und Vertretungsplan einschließlich Entfall und Raumänderungen.
- Schultermine und Leistungsnachweise; optional nach der Klasse filtern.
- Vorhandene Krankmeldungen lesen.
- Klassenbuch/Hausaufgaben, soweit erreichbar; hierfür sind Praxistests besonders wichtig.
- Lokale Aufgaben mit Fristen, Zahlungsbeträgen, Kommentaren und Bearbeitungsstatus.
- Lokal gespeicherte Daten bei Portalausfällen, mit Kennzeichnung des Datenstands.
- Bewusst freigegebene PDF-Downloads und lokal extrahierter Text.

Der Server benötigt keinen zusätzlichen KI-API-Schlüssel. Die Auswertung von
Stunden- und Vertretungsplänen geschieht lokal. Der verwendete MCP-Client kann
abgerufene Schuldaten allerdings an seinen Modellanbieter übertragen.

## Installation und Demo

Voraussetzung: **Python ab 3.13**.

```bash
git clone https://github.com/FabusMingAI/elternportal-mcp.git
cd elternportal-mcp
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install .
```

Unter Windows lautet der Aktivierungsbefehl `.venv\Scripts\activate`.

Im MCP-Client einen lokalen stdio-Server konfigurieren. Als Programm den
absoluten Pfad zu `.venv/bin/elternportal-mcp` eintragen; unter Windows
`.venv\Scripts\elternportal-mcp.exe`. Als Argument `--demo` verwenden.

Die Demo enthält ausschließlich erfundene Daten für zwei Kinder und ruft kein
Schulportal auf. Der direkte Aufruf `elternportal-mcp --demo` wartet auf einen
MCP-Client und zeigt deshalb kein interaktives Terminalmenü.

Konfigurationsbeispiele: [JSON](../examples/mcp-client.json) und
[TOML](../examples/mcp-client.toml). Pfade anpassen; `--demo` benötigt keine
Schulkonfiguration und kein Passwort.

## Eigene Schule einrichten

1. [config.example.json](../examples/config.example.json) in einen privaten
   Ordner kopieren, etwa `~/.config/elternportal-mcp/config.json`.
2. Unter `school` die Kennung vor `.eltern-portal.org` eintragen. Alternativ
   funktioniert die vollständige HTTPS-Adresse des Portals.
3. Unter `username` die Eltern-E-Mail und unter `password_env` den Namen einer
   eigens gewählten Umgebungsvariable eintragen, z. B. `SCHOOL_ONE_PASSWORD`.
4. Diese Variable im privaten Startkontext des MCP-Clients mit dem tatsächlichen
   Passwort belegen. Sie muss dem gestarteten Serverprozess zur Verfügung stehen.
5. Statt `--demo` die Argumente `--config /absoluter/pfad/config.json` verwenden.

Weitere Schulen als zusätzliche Einträge in `schools` konfigurieren. Pro Schule
ein Zugang; alle darüber sichtbaren Kinder werden automatisch aufgelistet.
Passwörter niemals in Issues, Chat-Nachrichten, Testdateien oder Git speichern.

Die Einstellungen erlauben unter anderem einen eigenen `data_dir`, Cache-Dauer
(`cache_ttl_seconds`, Standard 900), Rückblick (`lookback_days`, Standard 120)
und Anfrage-Timeout (`request_timeout_seconds`, Standard 30).

## Erste Schritte im Chat

Zuerst `list_children` verwenden und das richtige Kind anhand der zurückgegebenen
ID auswählen. Beispielaufträge:

- „Was steht bei Alex in der Schule an?“
- „Gibt es Unterrichtsausfall oder Raumänderungen?“
- „Welche Elternbriefe erwähnen den Museumsbesuch?“
- „Lege nach meiner Bestätigung eine lokale Zahlungsaufgabe über 12,50 Euro an.“

Aufgaben und Bearbeitungszustände gelten nur lokal im MCP-Server. „Erledigt“
übermittelt nichts an die Schule, bestätigt keinen Elternbrief und bezahlt keine
Rechnung. Der Server versendet keine Hintergrund-Erinnerungen.

## PDF-Abruf und Empfangsbestätigung

**Bereits der Download eines Elternbriefs kann im Portal seinen Empfang bestätigen.**

Deshalb sind Downloads zunächst deaktiviert. Das Auflisten von Briefen,
Aktualisieren und Lesen vorhandener Inline-Texte lädt keine PDFs herunter.

Für einen bewusst gewünschten Download `allow_pdf_downloads` lokal auf `true`
setzen und den Server neu starten. Zusätzlich muss der konkrete Toolaufruf
`confirm_possible_receipt=true` enthalten, nachdem du dem Abruf dieses Anhangs
zugestimmt hast. Ein bloßer Wunsch, einen Brief zu suchen, ist keine solche Zustimmung.

Die Texte werden lokal extrahiert und gespeichert. `get_cached_document` liest
sie anschließend ohne Portalaufruf. Die PDF-Datei selbst wird nicht dauerhaft
abgelegt. Bild-PDFs benötigen OCR, die diese Version nicht enthält.

Bei einem Fehler kann der Empfang bereits bestätigt worden sein, bevor die
Textextraktion scheiterte. Vor einem erneuten Versuch im Portal nachsehen.

## Datenstand, Speicherung und Grenzen

Normalerweise werden Daten bis zu 15 Minuten aus dem lokalen Cache gelesen.
Eine ausdrückliche Aktualisierung ist höchstens einmal pro Minute und Schule
im laufenden Prozess möglich. Der Server fragt nicht selbständig im Hintergrund ab.

Bei Fehlern bleiben bekannte Daten erhalten. Sowohl `source.stale` als auch
`section.status`, `section.retained` und `section.fetched_at` beachten:
Einzelne Bereiche können veraltet sein, während andere gerade aktualisiert wurden.
Ein erfolgreicher Abruf ohne Einträge ersetzt die vorherigen Einträge; dies ist
kein vollständiges historisches Archiv.

Die SQLite-Datenbank enthält unverschlüsselte Schultexte, extrahierte PDF-Texte
und lokale Aufgaben. Standardpfad ist `~/.local/share/elternportal-mcp`, für die
Demo `~/.local/share/elternportal-mcp-demo`. Unter POSIX wird die Datenbank mit
Dateirechten 0600 angelegt. Ordner und Sicherungskopien entsprechend schützen.
Zugangspasswörter und Sitzungscookies werden dort nicht gespeichert.

Krankmeldungen absenden, Beurlaubungen beantragen, Nachrichten versenden,
Abstimmen und Sprechstunden buchen sind nicht enthalten. Eine Verbindung mit
Schulmanager Online oder dem Schüler-Portal ist ebenfalls nicht enthalten.

Bei Layoutänderungen kann ein Bereich ausfallen. Bitte nur mit synthetischen
oder sorgfältig anonymisierten Beispielen melden. Auch unsichtbare Felder einer
HTML-Seite können persönliche IDs, CSRF-Werte oder Dateizugänge enthalten.

Weitere Informationen: [README](../README.md), [Roadmap](../ROADMAP.md),
[Datenschutz und Sicherheit](../SECURITY.md).
