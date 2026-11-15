# Eltern-Portal MCP mit ChatGPT verbinden

Stand: 15. November 2026. Der Server aus diesem Repository spricht **stdio**.
ChatGPT startet ihn nicht aus einer Claude-JSON-Datei. Diese Anleitung verbindet
ihn über **Secure MCP Tunnel**; ein eigener öffentlicher HTTP-Server ist dafür
nicht erforderlich. Der Tunnel ist zusätzliche Software von OpenAI und nicht
Bestandteil dieses Pakets. [Transport und Voraussetzungen bei OpenAI](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels).

## 1. Zugang und lokale Installation prüfen

Die [aktuelle ChatGPT-Hilfe](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt)
beschreibt eigene MCP-Verbindungen für **Business und Enterprise/Edu im Web**.
Die Berechtigung zum Erstellen muss im vorgesehenen Workspace vorhanden sein.
Diese Anleitung verspricht keine entsprechende Freischaltung für andere Tarife.
Fehlt die Funktion im Konto, löst eine Änderung am Elternportal-Server das nicht.

Für den Tunnel werden außerdem eine Platform-Organisation, ein Tunnel und ein
Runtime-API-Key benötigt. Erstellen/Ändern erfordert **Tunnels Read + Manage**,
die Nutzung **Tunnels Read + Use**. Platform-Organisation und ChatGPT-Workspace
müssen dem Tunnel passend zugeordnet sein. Ein ChatGPT-Abonnement allein ersetzt
diese Voraussetzungen nicht. [Berechtigungen und Zuordnung](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels).

Das Python-Paket zuerst auf dem eigenen Rechner installieren:
[Paketinstallation für macOS und Windows](CLAUDE_DESKTOP.md#1-paket-installieren).
**Nur diesen Installationsabschnitt verwenden; Claude Desktop wird hier nicht benötigt.**

## 2. Tunnel und tunnel-client vorbereiten

1. In den [Platform-Tunneleinstellungen](https://platform.openai.com/settings/organization/tunnels)
   einen geeigneten privaten Tunnel auswählen oder erstellen. Dessen `tunnel_id`
   notieren und die Zuordnung zum Ziel-Workspace kontrollieren.
2. Einen Runtime-Key mit den erforderlichen Tunnelrechten beschaffen. Für den
   dauerhaften Betrieb keinen Admin-Key verwenden.
3. Den unterstützten `tunnel-client` über diese Einstellungsseite oder die
   [offiziellen Releases](https://github.com/openai/tunnel-client/releases/latest)
   für das eigene Betriebssystem und die Prozessorarchitektur herunterladen.
   Die Programmdatei so ablegen, dass der Befehl `tunnel-client` erreichbar ist.
4. Die installierte Version mit `tunnel-client help quickstart` prüfen.

Diese Schritte folgen dem [offiziellen Onboarding](https://github.com/openai/tunnel-client/blob/master/docs/onboarding.md).
Für plattformspezifische Installationsdetails und geänderte CLI-Optionen ist
dessen aktuelle Anleitung maßgeblich. Noch keinen eingebauten Stub oder fremden
MCP-Demoserver starten: Im folgenden Schritt wird unser Elternportal-Prozess angebunden.

## 3. Zuerst die Elternportal-Demo anbinden

Der Tunnel muss `python` aus unserer `.venv` starten. Für **dieses Terminal**
zuerst den Suchpfad setzen und den Interpreter prüfen.

macOS, bash (gegebenenfalls zuerst `bash` eingeben):

```bash
export PATH="$HOME/elternportal-mcp/.venv/bin:$PATH"
python -m elternportal_mcp --version
read -r -s -p "Tunnel-Runtime-Key: " CONTROL_PLANE_API_KEY
printf '\n'
export CONTROL_PLANE_API_KEY
```

Windows, PowerShell:

```powershell
$env:PATH = "$env:USERPROFILE\elternportal-mcp\.venv\Scripts;" + $env:PATH
python -m elternportal_mcp --version
$TunnelKey = Read-Host "Tunnel-Runtime-Key" -AsSecureString
$env:CONTROL_PLANE_API_KEY = [System.Net.NetworkCredential]::new('', $TunnelKey).Password
Remove-Variable TunnelKey
```

Den Key nur in die verdeckte lokale Eingabe eingeben. Er gehört weder in Chat,
Git, Profiltext noch Kommandozeilenargumente. Die folgenden CLI-Aufrufe gelten
für beide Systeme. `DEINE_TUNNEL_ID` durch die tatsächlich ausgegebene ID ersetzen:

```text
tunnel-client init --sample sample_mcp_stdio_local --profile elternportal-demo --tunnel-id DEINE_TUNNEL_ID --control-plane-api-key-ref env:CONTROL_PLANE_API_KEY --mcp-command "python -m elternportal_mcp --demo"
tunnel-client doctor --profile elternportal-demo --explain
tunnel-client run --profile elternportal-demo
```

Das Profil enthält einen **Verweis** auf die Key-Umgebungsvariable. Der
`init`-/`doctor`-/`run`-Ablauf und die stdio-Optionen sind in der
[Konfigurationsreferenz](https://github.com/openai/tunnel-client/blob/master/docs/configuration.md)
beschrieben. `doctor` muss die Verbindungsvoraussetzungen bestätigen; den
laufenden Prozess während der ChatGPT-Nutzung offen lassen. Nach einem neuen
Terminalstart Suchpfad und Key erneut bereitstellen.

## 4. In ChatGPT hinzufügen

Im vorgesehenen Workspace auf **Plugins → + → Add custom MCP server** gehen.
Als Namen beispielsweise `Eltern-Portal Demo` eintragen. Unter **Connection**
**Tunnel** und denselben Tunnel auswählen beziehungsweise seine ID eingeben.
Die angebotenen Authentifizierungseinstellungen prüfen: Unser lokaler
stdio-Server hat keine eigene OAuth-Anmeldung. Schulpasswort und Runtime-Key
werden hier nicht als Server-Login eingetragen.

Nach Prüfung des angezeigten Risikohinweises mit **Create as a plugin** anlegen.
Die aktuelle Oberfläche verlangt laut OpenAI kein vorab aktiviertes Developer
Mode; ältere Oberflächen können andere Menübezeichnungen zeigen.
[Offizieller Einrichtungsablauf](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt).

Die Verbindung installieren/aktivieren, einen neuen Chat beginnen und das Plugin
mit `@` auswählen. Dann nacheinander aufrufen lassen:

1. `get_health`: Serverstatus und Version.
2. `list_children`: **Alex Beispiel** und **Robin Beispiel**.
3. `get_appointments` für `demo:1`: Demo-Schulaufgabe.
4. `get_daily_plan` für `demo:1` am nächsten Montag: Demo-Stundenplan.

Die Werkzeugerkennung des aktuellen Servers liefert 42 Werkzeuge. Erst ein
tatsächlich erfolgreicher Werkzeugaufruf zeigt, dass ChatGPT den Server erreicht;
ein gespeichertes Profil oder ein grüner lokaler Prozess allein reicht nicht.

## 5. Auf die eigene Schule wechseln

Die private [Schulkonfiguration](../examples/config.example.json) einrichten:
Kennung, Eltern-E-Mail und `password_env`, beispielsweise `SCHOOL_ONE_PASSWORD`.
Siehe auch [eigene Schule einrichten](DEUTSCH.md#eigene-schule-einrichten).

Damit das Profil keine empfindlichen oder kompliziert zitierten Dateipfade im
Startbefehl braucht, setzt es `ELTERNPORTAL_CONFIG` als Umgebungsvariable. In
demselben Terminal wie der Runtime-Key:

macOS, bash:

```bash
export ELTERNPORTAL_CONFIG="$HOME/.config/elternportal-mcp/config.json"
read -r -s -p "Elternportal-Passwort: " SCHOOL_ONE_PASSWORD
printf '\n'
export SCHOOL_ONE_PASSWORD
```

Windows, PowerShell:

```powershell
$env:ELTERNPORTAL_CONFIG = "$env:APPDATA\ElternPortalMCP\config.json"
$SchoolPassword = Read-Host "Elternportal-Passwort" -AsSecureString
$env:SCHOOL_ONE_PASSWORD = [System.Net.NetworkCredential]::new('', $SchoolPassword).Password
Remove-Variable SchoolPassword
```

Den Demo-Tunnelprozess mit Strg+C beenden. Ein zweites **lokales Profil** für
denselben Tunnel erstellen, das dieses Mal ohne `--demo` startet:

```text
tunnel-client init --sample sample_mcp_stdio_local --profile elternportal-school --tunnel-id DEINE_TUNNEL_ID --control-plane-api-key-ref env:CONTROL_PLANE_API_KEY --mcp-command "python -m elternportal_mcp"
tunnel-client doctor --profile elternportal-school --explain
tunnel-client run --profile elternportal-school
```

Die Profile sind zwei Alternativen; bei stdio nur **einen** aktiven
`tunnel-client` für dieselbe Tunnel-ID betreiben. Der gestartete Kindprozess
muss Suchpfad, `ELTERNPORTAL_CONFIG` und Passwortvariable aus seinem Startkontext
erhalten. Stimmen Variablen oder Interpreter nicht, zuerst dies lokal beheben.
Bei jeder neu gestarteten Shell die Variablen wieder setzen. Die
[stdio-Betriebsgrenzen](https://github.com/openai/tunnel-client/blob/master/docs/configuration.md#stdio-deployment-limits)
erläutern, weshalb parallele Instanzen derselben Tunnel-ID nicht unterstützt sind.

Die ChatGPT-Verbindung verwendet weiter denselben Tunnel; Name und Beschreibung
gegebenenfalls von „Demo“ auf „Eltern-Portal“ ändern. In einem neuen Chat
`list_children` ausführen und die echten Kind-IDs auswählen. Erscheinen weiterhin
Demo-Kinder, läuft noch ein Prozess mit `--demo` oder der falsche Tunnel ist ausgewählt.

PDF-Downloads bleiben deaktiviert, bis ein konkreter Abruf bewusst gewünscht
ist. Sie können eine Empfangsbestätigung auslösen. Schultexte, die über die
Verbindung abgerufen werden, verlassen den lokalen Rechner und stehen ChatGPT
zur Verarbeitung zur Verfügung. Ein privater Tunnel bedeutet nicht, dass die
Toolergebnisse ausschließlich lokal bleiben.

## Fehlersuche

| Problem | Nächster Schritt |
|---|---|
| Menü zum Hinzufügen fehlt | Konto/Workspace und Erstellungsberechtigung prüfen; keine allgemeine Verfügbarkeit für jeden Tarif annehmen |
| Tunnel nicht auswählbar | Platform-/Workspace-Zuordnung, richtige Organisation und Tunnel-Use-Rechte prüfen |
| `doctor` meldet fehlenden Key | Runtime-Key im selben Terminal setzen; ein neues Fenster übernimmt temporäre Variablen nicht automatisch |
| Python/Modul nicht gefunden | Suchpfad erneut setzen und `python -m elternportal_mcp --version` prüfen |
| Eigene Schule meldet fehlende Zugangsdaten | `ELTERNPORTAL_CONFIG`, Schulkennung und die mit `password_env` benannte Variable im Kindprozess prüfen |
| Werkzeugaufrufe gehen nach Neustart nicht | Tunnelprozess laufen lassen, Verbindung neu aufbauen und Werkzeugerkennung wiederholen |
| Lange erste Schulabfrage / Timeout | Der Tunnel hat aktuell eine Standardfrist von 120 Sekunden; ein langsamer frischer Portalabruf kann länger dauern. Demo gegenprüfen und gegebenenfalls den [lokalen Hintergrundworker](HA_BRIDGE.md#laufzeit-und-dateien) zum Vorabruf des Caches einsetzen |
| `sampling` nicht unterstützt | `analyze_item` mit lokalen Regeln oder `save_analysis` verwenden; erfolgreiche Werkzeugaufrufe garantieren keine Sampling-Unterstützung |

Die Frist und die laufzeitabhängige Erreichbarkeit sind in der
[Tunnel-Dokumentation](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
beschrieben. Im Fehlerfall keine Tokens, Passwörter oder unbereinigten
Schulantworten veröffentlichen.

## Prüfstand und Aktualisierungen

Geprüft sind die lokale stdio-Schnittstelle und synthetische Werkzeugaufrufe.
Diese Anleitung ist mit den oben verlinkten offiziellen Quellen abgeglichen;
ein Ende-zu-Ende-Test mit einem persönlichen OpenAI-Tunnel und einem tatsächlichen
ChatGPT-Workspace wurde für dieses Projekt noch nicht durchgeführt. Daher wird
die reale ChatGPT-Verbindung hier nicht als bereits erfolgreich getestet behauptet.

Für ein Paketupdate den Tunnelprozess stoppen, das Repository aktualisieren und
das Paket erneut mit dem `.venv`-Python installieren. Danach Variablen im Terminal
bereitstellen, `doctor` ausführen und den passenden Tunnelprozess neu starten.
Die Schuleinstellungen und lokale SQLite-Datenbank müssen dafür nicht gelöscht werden.

Zurück: [Deutsche Übersicht](DEUTSCH.md) · [Claude Desktop](CLAUDE_DESKTOP.md).
