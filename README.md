# Alexa Bridge Manager

Home Assistant Custom Integration zur vollständigen UI-Verwaltung der manuellen
Alexa Smart Home Integration (`alexa.smart_home`) – ohne `configuration.yaml`
zu editieren und ohne Neustart von Home Assistant.

## Features

- [x] Config Flow: Endpoint (EU/NA/FE/eigene URL), Client ID, Client Secret
- [x] Options Flow: eine durchsuchbare Entity-Auswahl (HA-natives
      Multi-Select, filterbar nach Name/Bereich/Domain) statt einer langen
      Checkbox-Liste, danach optional Alexa-Namen nur für die gewählten
      Entities vergeben, inkl. Erkennung doppelter Alexa-Namen
- [x] Sofortige Übernahme der Änderungen ohne HA-Neustart oder Reload
- [x] Automatischer Alexa-Discovery-Push (`AddOrUpdateReport`/`DeleteReport`)
      wenn sich die Freigabe ändert
- [x] Diagnostics-Karte mit Anzahl freigegebener/benannter Entities
      (Secrets maskiert)

## ⚠️ Wichtig: nicht parallel zu `alexa: smart_home:` in configuration.yaml

Home Assistants eingebaute `alexa`-Komponente ist rein YAML-konfiguriert und
registriert den HTTP-Endpoint `/api/alexa/smart_home` einmalig beim Start.
Diese Integration übernimmt genau diesen Endpoint selbst, damit Änderungen
ohne Neustart wirksam werden. Beide können nicht gleichzeitig aktiv sein.

**Migration:** Entferne den `smart_home:`-Unterblock aus deinem `alexa:`
Abschnitt in `configuration.yaml` (andere Abschnitte wie `flash_briefings`
kannst du behalten) und starte HA einmal neu, bevor du diese Integration
einrichtest. Ist der Block noch vorhanden, bricht das Setup mit einer
Reparatur-Meldung ("Alexa Smart Home Endpoint bereits belegt") ab.

## Installation

### Über HACS (Custom Repository)

1. HACS → drei Punkte oben rechts → *Benutzerdefinierte Repositories*
2. Repository-URL `https://github.com/Knabbiii/alexa_bridge_manager` eintragen,
   Kategorie **Integration**
3. "Alexa Bridge Manager" installieren und Home Assistant neu starten

### Manuell

1. Ordner `custom_components/alexa_bridge_manager` in dein HA-Config-Verzeichnis
   nach `custom_components/` kopieren
2. Home Assistant neu starten

## Einrichtung

Einstellungen → Geräte & Dienste → Integration hinzufügen → **Alexa Bridge Manager**

Benötigt werden die Zugangsdaten deines Alexa Smart Home Skills aus der
[Alexa Developer Console](https://developer.amazon.com/alexa/console/ask)
(Smart Home → Account Linking):

- Event Gateway (Region auswählen oder eigene URL)
- Client ID
- Client Secret

Anschließend über Einstellungen → Geräte & Dienste → Alexa Bridge Manager →
**Konfigurieren** jederzeit Entities freigeben/umbenennen.

## Voraussetzung

Die Home-Assistant-Core-Integration `alexa` muss grundsätzlich verfügbar sein
(Standard in jeder HA-Installation), darf aber keinen `smart_home:`-Block mehr
in `configuration.yaml` haben (siehe Migrationshinweis oben).

## Entwicklung / Tests

```bash
python3 -m pip install --user pytest-homeassistant-custom-component
python3 -m pytest tests/ -q
```

## Mitwirken / Issues

Bugs und Feature-Wünsche bitte über den Issue-Tracker dieses Repositories melden.
