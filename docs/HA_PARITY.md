# Funktionsvergleich: HA-Integration und MCP 0.2.0

Verglichen am 15.11.2026 mit [ha-schulmanager](https://github.com/FabusMingAI/ha-schulmanager),
Commit `fc1357caba5677358b70731650932b95140ad586` (Integrationsversion 0.14.11).

| Funktion der HA-Integration | MCP 0.2.0 |
|---|---|
| Mehrere Schulen und Kinder, Portalbereiche lesen | Bereits in 0.1 vorhanden |
| Automatische Aufgaben für unbestätigte Briefe/offene Umfragen | Neu: lokaler Abgleich; beobachtete Portalbestätigung/Abstimmung erledigt die Aufgabe |
| Aufgaben, Beträge, IBAN, Empfänger, Verwendungszweck, Termine aus Mitteilungen | Neu: lokale Regeln sowie strukturierte KI-Auswertung mit Pflichtbelegen; automatische Vorschläge sind als prüfbedürftig markiert |
| KI-Anbieter über HA AI Task | Optional über die HA-Brücke; alternativ MCP-Sampling oder vom Client vorbereitete Auswertung |
| Mehrsprachige Zusammenfassungen DE/EN/ES/CA | Neu: speichern und übersetzen; Übersetzung verändert keine Aufgaben, Kommentare oder Termine |
| Automatische Nachanalyse und fehlende Übersetzungen | Optionaler HA-KI-Hintergrundbetrieb, maximal drei Versuche mit sechs Stunden Abstand |
| Gelesen/ungelesen, Bearbeitungsstatus, Kommentare | Neu: separater lokaler Lesestatus; bestehender Bearbeitungsstatus bleibt erhalten |
| Geänderte Mitteilungen wieder ungelesen | Neu: Inhaltsvergleich ignoriert reine Leerraumänderungen; lokale Aufgabenänderungen bleiben erhalten |
| Dauerhaftes Mitteilungsarchiv | Neu: Texte/Metadaten bleiben nach Verschwinden aus dem aktuellen Abruf erhalten; begrenztes Änderungsprotokoll |
| Originaldateien pro Kind und Schuljahr | Neu bei ausdrücklich freigegebenem Download; auch Nicht-PDF-Anhänge, nie automatisch geöffnet |
| Aufgabenkommentare, Zahlungsdetails, Wiedervorlage | Neu: Typ, Empfänger, IBAN, Verwendungszweck; `snooze_task` ändert nur die Erinnerung, nicht die Frist |
| Gemeinsamer Kalender aus Briefen, Aufgaben, Portal, Ausfällen und Krankmeldungen | Neu: `get_calendar` |
| Kalenderarchiv | Neu: Einträge ausblenden/wiederherstellen; offene Aufgaben und Erinnerungen bleiben bestehen |
| Einzeltermin als ICS/Google-Kalenderformular | Neu: stabile UID, UTF-8-Faltung, Erinnerungsalarm; Tool öffnet keinen Link und schreibt keinen externen Kalender |
| Angereicherter Stundenplan und persönliche Kursinformationen | Neu: übernommene HA-Nachweislogik, vorhandene Kursanmeldungen nur lesend; keine geratenen Kurszuordnungen |
| Vertretungen mit Zeiten, eindeutigem Fach und Lehrernamen | Neu: aus Stundenplan/Schulinformationen abgeleitet; Namensanzeige konfigurierbar |
| Tagesplan mit Änderungen und Prüfungshinweisen | Neu: `get_daily_plan`; fachlich erkennbare Prüfungen am passenden Unterricht, unbekannte Zuordnung nur auf Tagesebene |
| WebUntis ergänzend | Optionaler Abruf eines pro Kind zugeordneten HA-Kalenders, unterstützte JSON-Beschreibung wie in HA; Dublettenabgleich und veraltete Daten bei Ausfall |
| Ampel, nächste Frist, ungelesene Nachrichten, offene Zahlungen | Neu: `get_statistics`, `get_family_overview`, erweiterter `get_overview` |
| Krankmeldungen im Schuljahr | Neu: eindeutige Mo–Fr-Tage aus vorhandenen Meldungen, Überschneidungen zählen einmal; Ferien werden nicht abgezogen |
| Erinnerungen und Morgenübersicht | Neu: Vorschau ohne Versand; Fristen 3/1/0 Tage vorher, überfällige täglich; heutige/morgige Termine und Prüfungen |
| Push, Sprachausgabe | Optional über konfigurierte HA-Dienste; expliziter Toolauftrag oder lokale Freigabe für Hintergrundversand, Ruhezeiten für Hintergrundsprache |
| Erledigt/Morgen-erinnern am Handy | Optional: HA-Companion-Aktionen; Rückmeldungen benötigen laufenden Hintergrundprozess und HA-WebSocket |
| Neue Mitteilungen/Vertretungen melden | Neu: lokale Änderungswarteschlange, ruhiger Erstimport, optionale Push-Zustellung |
| Regelmäßiger Abruf, dauerhafter Betrieb | Neu: opt-in im MCP-Prozess oder separater `--worker`; Worker-Sperre verhindert doppelte Hintergrundjobs bei gemeinsamem Datenverzeichnis |
| Dashboardkarten, HA-Sensoren, To-do-/Kalenderentitäten, automatische Lovelace-Einrichtung, HA-Migrationsdialoge | Bleiben Bestandteil der HA-Integration. Der MCP bietet ihre Informationen und Arbeitsvorgänge als Werkzeuge an, erzeugt selbst keine Lovelace-Oberfläche oder HA-Entitäten |

## Neue MCP-Werkzeuge

`mark_items_read`, `archive_item`, `list_archive`, `analyze_item`, `save_analysis`,
`get_analysis`, `translate_summary`, `snooze_task`, `get_calendar`, `archive_event`,
`export_event`, `get_daily_plan`, `get_statistics`, `get_family_overview`,
`get_reminders`, `get_digest`, `refresh_webuntis`, `send_briefing`,
`download_attachment`, `get_saved_attachment`, `get_changes`, `acknowledge_changes`.

Zusammen mit den bisherigen 20 Werkzeugen stehen **42 Werkzeuge** bereit.

## Einordnung

Das sind funktionale Entsprechungen für MCP, keine Kopie der HA-Benutzeroberfläche.
Ein MCP-Client muss Sampling unterstützen, um selbst einen Modellaufruf für
`analyze_item(method="sampling")` auszuführen. Andernfalls kann er eine passende
Auswertung über `save_analysis` speichern oder lokale Regeln nutzen. HA bleibt
optional; nur die ausdrücklich darüber angebundenen Dienste setzen HA voraus.

Der Stand ist weiterhin eine Community-Vorabversion. Tests verwenden synthetische
Daten und simulierte HA-Dienste. Echte Portal-, HA-KI-, WebUntis- und Handy-/Sprachabläufe
müssen mit dem eigenen Zugang geprüft werden. Es werden weiterhin keine
Krankmeldungen, Nachrichten, Buchungen, Stimmen oder Zahlungen an die Schule übermittelt.
