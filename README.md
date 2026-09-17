# Alexa Bridge Manager

Home Assistant Custom Integration zur vollständigen UI-Verwaltung der manuellen
Alexa Smart Home Integration (`alexa.smart_home`) – ohne `configuration.yaml`
zu editieren und ohne Neustart von Home Assistant.

> **Status:** In aktiver Entwicklung. Aktuell implementiert: Ersteinrichtung
> (Config Flow) mit Endpoint/Client ID/Client Secret. Die Verwaltung der
> freigegebenen Entities (Options Flow) folgt in einer der nächsten Versionen.

## Features (geplant/in Arbeit)

- [x] Config Flow: Endpoint (EU/NA/FE/eigene URL), Client ID, Client Secret
- [ ] Options Flow: Entities durchsuchen, freigeben und für Alexa umbenennen
- [ ] Sofortige Übernahme der Änderungen ohne HA-Neustart
- [ ] Übersicht, wie viele Entities aktuell freigegeben sind

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

## Voraussetzung

Die Home-Assistant-Core-Integration `alexa` muss grundsätzlich verfügbar sein
(Standard in jeder HA-Installation). Diese Custom Integration übernimmt die
Konfiguration, die sonst manuell in `configuration.yaml` gepflegt werden müsste.

## Mitwirken / Issues

Bugs und Feature-Wünsche bitte über den Issue-Tracker dieses Repositories melden.
