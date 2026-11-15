# Eltern-Portal MCP in Claude Desktop einrichten

Stand: 15. November 2026. Diese Anleitung verwendet die manuelle lokale
stdio-Anbindung. Sie benötigt die **Claude-Desktop-App**, Git und **Python 3.13+**.
Für die Demo sind weder Schulzugang noch zusätzlicher KI-API-Schlüssel nötig.
Der Weg ist nicht mit einem Remote-Connector in Claude Web oder einer
installierbaren `.mcpb`-Erweiterung gleichzusetzen; dieses Projekt liefert derzeit
kein solches Erweiterungspaket.

## 1. Paket installieren

macOS, Terminal:

```bash
git clone https://github.com/FabusMingAI/elternportal-mcp.git "$HOME/elternportal-mcp"
python3.13 -m venv "$HOME/elternportal-mcp/.venv"
"$HOME/elternportal-mcp/.venv/bin/python" -m pip install "$HOME/elternportal-mcp"
"$HOME/elternportal-mcp/.venv/bin/python" -m elternportal_mcp --version
```

Windows, PowerShell:

```powershell
git clone https://github.com/FabusMingAI/elternportal-mcp.git "$env:USERPROFILE\elternportal-mcp"
py -3.13 -m venv "$env:USERPROFILE\elternportal-mcp\.venv"
& "$env:USERPROFILE\elternportal-mcp\.venv\Scripts\python.exe" -m pip install "$env:USERPROFILE\elternportal-mcp"
& "$env:USERPROFILE\elternportal-mcp\.venv\Scripts\python.exe" -m elternportal_mcp --version
```

Die Versionsabfrage muss ohne Importfehler enden, beim aktuellen Release mit
`0.2.0`. Wenn das Repository bereits vorhanden ist, diesen Schritt nicht erneut
klonen. Für Updates siehe unten. Die Umgebung muss nicht aktiviert werden;
alle Beispiele verwenden den Python-Interpreter aus `.venv` direkt.

## 2. Claude-Konfiguration öffnen

Claude vollständig beenden und die Datei `claude_desktop_config.json` öffnen:

| System | Datei |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

Je nach App-Version ist sie auch über **Settings → Developer → Edit Config**
zugänglich. Falls Ordner oder Datei fehlen, eine UTF-8-JSON-Datei dort anlegen.
Existiert bereits eine Konfiguration, nur den Eintrag `mcpServers.elternportal`
ergänzen und andere Server/Einstellungen erhalten. Die Dateipfade und der
manuelle Anschluss sind im [offiziellen MCP-Leitfaden](https://modelcontextprotocol.io/docs/develop/connect-local-servers)
beschrieben; die Oberfläche kann je nach Claude-Version anders aussehen.

## 3. Zuerst die Demo verbinden

Passende Vorlage verwenden und `DEIN_NAME` beziehungsweise die Pfade ersetzen:

- [macOS: Demo-Konfiguration](../examples/claude-desktop-demo.macos.json)
- [Windows: Demo-Konfiguration](../examples/claude-desktop-demo.windows.json)

Beispiel macOS:

```json
{
  "mcpServers": {
    "elternportal": {
      "command": "/Users/DEIN_NAME/elternportal-mcp/.venv/bin/python",
      "args": ["-m", "elternportal_mcp", "--demo"]
    }
  }
}
```

Im JSON immer **absolute Pfade** verwenden; `~`, `$HOME` und
`%USERPROFILE%` nicht ungeprüft als JSON-Pfade übernehmen. In Windows-JSON
Backslashes verdoppeln, wie in der Vorlage. `command` enthält nur den Pfad zur
Programmdatei, die einzelnen Argumente stehen in `args`.

Claude neu starten. Den Server nicht zusätzlich von Hand als zweite
stdio-Instanz starten: Claude startet seinen eigenen Prozess.

## 4. Verbindung im Chat prüfen

Den lokalen Server in Claudes Werkzeug-/Connector-Auswahl aktivieren. Sein
Status und die Logs sind je nach Version unter **Settings → Desktop app →
Extensions/Manage → Local MCP servers** oder im älteren Bereich
**Settings → Developer** erreichbar. Diese Varianten nennt die
[Claude-Hilfe](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop).

In einem neuen Chat nacheinander fragen:

1. „Nutze den Elternportal-Server und rufe `get_health` auf.“
2. „Rufe `list_children` auf und zeige die Demo-Kinder.“
3. „Zeige mit `get_daily_plan` den Tagesplan für `demo:1` am nächsten Montag.“

Erwartet werden ein Serverstatus und die beiden erfundenen Kinder **Alex Beispiel**
und **Robin Beispiel**. Der aktuelle Server stellt 42 Werkzeuge bereit; welche
Claude davon anzeigt, hängt auch von der Werkzeugauswahl und ihren Grenzen ab.
Ein laufender Prozess allein beweist noch keine erfolgreiche Verbindung.

## 5. Auf den eigenen Schulzugang wechseln

Eine private Datei `config.json` aus [dieser Vorlage](../examples/config.example.json)
erstellen. Empfohlene Ablage:

- macOS: `~/.config/elternportal-mcp/config.json`
- Windows: `%APPDATA%\ElternPortalMCP\config.json`

`school` ist die Kennung vor `.eltern-portal.org`, `username` die Eltern-E-Mail.
`password_env` bleibt beispielsweise `SCHOOL_ONE_PASSWORD`. Weitere Schulen
erhalten eigene Einträge und eigene Passwortvariablen.

Den Demo-Eintrag in Claude durch die passende Schulvorlage ersetzen:

- [macOS: Schulzugang](../examples/claude-desktop-school.macos.json)
- [Windows: Schulzugang](../examples/claude-desktop-school.windows.json)

Pfade anpassen und **nur in der privaten Claude-Datei** den Passwort-Platzhalter
unter `env` ersetzen. Diese manuelle JSON-Variante speichert das Passwort als
Klartext im lokalen Clientprofil. Die Datei entsprechend schützen, nicht ins
Repository kopieren und nicht in Screenshots oder Fehlerberichte aufnehmen.
Die Schuldatei selbst enthält nur den Namen der Passwortvariablen.

`--demo` entfällt; stattdessen stehen `--config` und der absolute Schuldateipfad
in `args`. Claude vollständig neu starten. Mit `list_children` die tatsächlichen
Kind-IDs ermitteln und erst dann Stundenplan, Vertretungen oder Schulaufgaben
abfragen. Die Demo-IDs passen nicht zum Schulzugang.

PDF-Downloads bleiben zunächst deaktiviert. Das Abrufen eines PDFs kann dessen
Empfang an der Schule bestätigen. Für den bewussten Abruf gelten die
[Downloadregeln](DEUTSCH.md#pdf-abruf-und-empfangsbestätigung). Rückgegebene
Schultexte können vom verwendeten KI-Client an dessen Modellanbieter übermittelt werden.

## Fehlersuche und Updates

| Problem | Prüfen |
|---|---|
| Server fehlt | JSON gültig, richtige Datei, Claude vollständig neu gestartet? |
| Programm nicht gefunden | Existiert genau der absolute `command`-Pfad aus der gewählten Vorlage? |
| `No module named elternportal_mcp` | Paket in genau diese `.venv` installieren; nicht versehentlich System-Python verwenden |
| Keine Ausgabe beim manuellen Start mit `--demo` | Normal: stdio wartet auf einen MCP-Client; mit Strg+C beenden |
| `Credentials missing` / ungültige Konfiguration | Stimmen Schuldateipfad, `password_env` und Claudes `env`-Eintrag überein? |
| Schule nicht erreichbar | Zuerst die Demo prüfen, danach Portalzugang und `get_health`; MFA ist nicht implementiert |
| Sampling nicht verfügbar | Lokale Regeln oder `save_analysis` verwenden; Sampling ist eine gesonderte Clientfähigkeit |

Für Updates Claude beenden, im Repository `git pull --ff-only` ausführen und
mit dem oben verwendeten `.venv`-Python erneut `-m pip install /absoluter/pfad/zum/repository`
ausführen. Danach Claude neu starten. Bei veralteter Werkzeugliste erneut
verbinden. Logs vor einer Weitergabe auf personenbezogene Daten prüfen.

## Prüfstand

Die stdio-Konfiguration und die Werkzeuge wurden automatisiert mit einem
MCP-Client getestet. Ein vollständiger GUI-Durchlauf in Claude Desktop sowie
der Abruf eines echten Schulzugangs sind damit nicht nachgewiesen.

Weiter: [ChatGPT-Anleitung](CHATGPT.md) · [Deutsche Übersicht](DEUTSCH.md).
