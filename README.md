# email_to_trilium

Ein Docker-Bot, der ein IMAP-Postfach überwacht, E-Mails ausliest und diese automatisch als formatierte HTML-Notizen inkl. Anhängen via ETAPI in **Trilium Next** ablegt.

## Features
- 🔄 **5-Minuten-Intervall:** Läuft vollautomatisch im Docker-Container.
- 📂 **Target-Routing:** Per `[target:Ordnername]` im Betreff landen Mails direkt im richtigen Ordner. Wenn er fehlt, wird ein Standardordner genutzt.
- 📁 **Automatisches Anlegen:** Nicht existierende Ordner werden dynamisch erstellt.
- 📎 **Anhänge:** Werden vollautomatisch als Child-File-Notes an die Hauptnotiz angehängt.
- 🧼 **Bereinigung:** Erfolgreiche Mails werden gelöscht, fehlerhafte Mails landen im IMAP-Ordner `Fehler`.
- 🚨 **Alarmsystem:** Sendet bei Fehlern eine Benachrichtigung per E-Mail.

## Lokales Testen (VS-Code)
1. Kopiere `.env.example` zu `.env` und fülle deine echten Daten aus.
2. Achte darauf, dass `DOCKER_MODE=false` in der `.env` steht.
3. Installiere Abhängigkeiten: `pip install -r requirements.txt`
4. **Tests ausführen:** `python -m unittest discover tests`
5. **Skript einmalig lokal ausführen:** `python src/main.py`

## Produktion (Docker Compose)
1. Setze in deiner `.env` das Attribut `DOCKER_MODE=true` (oder entferne die Zeile, Docker erzwingt es via Dockerfile).
2. Starte den Container:
   ```bash
   docker-compose up -d --build
   ```
3. Logs einsehen:
   ```bash
   docker logs -f email_to_trilium
   ```
