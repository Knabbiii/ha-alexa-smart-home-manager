## Alexa Bridge Manager

Verwalte, welche Entities über die manuelle Alexa Smart Home Integration
(`alexa.smart_home`) freigegeben sind – komplett über die Home Assistant UI,
ohne `configuration.yaml`-Edits und ohne Neustart.

**Wichtig:** Ersetzt den `smart_home:`-Block deiner `alexa:`-YAML-Konfiguration,
läuft nicht parallel dazu. Details siehe README.

### Features
- Ersteinrichtung per Config Flow (Endpoint/Client ID/Client Secret)
- Entity-Freigabe & Alexa-Namen per Options Flow, paginiert nach Domain
- Änderungen wirken sofort, inkl. automatischem Alexa-Discovery-Push
- Diagnostics-Karte mit Übersicht der freigegebenen Entities
