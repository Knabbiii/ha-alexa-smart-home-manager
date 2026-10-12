# Changelog

Every version lists its changes as `New:`, `Changed:`, `Fixed:` or `Removed:`.
The same lines are used as the release notes HACS shows in Home Assistant.

## 1.0.0

- New: Reconfigure flow. Change the event gateway or credentials without removing the integration, which would make Alexa forget every device.
- New: "Alexa linked" and "Sync status" diagnostic entities, and a "Resync with Alexa" button that resends every exposed entity.
- New: Repair issue, with a one-click fix, when an exposed entity no longer exists.
- New: Renaming an exposed entity ID in Home Assistant carries over its exposure and Alexa name.
- New: The naming step shows each entity's friendly name and area.
- Changed: Renamed to **Alexa Smart Home Manager** (was Alexa Bridge Manager). Only the display name changed. The domain, existing entities and settings stay as they are.
- Changed: The sync state is stored, so a restart no longer resends everything and removals made while the skill was not linked are not forgotten.
- Changed: Entities are pushed to Alexa automatically once account linking completes.
- Changed: Alexa names must be unique, ignoring case. Overlapping names such as "Lamp" and "Floor Lamp" are fine. An entity's Home Assistant name counts when it has no custom name.
- Changed: The locale is `en-US` (was `de-DE`).
- Changed: The manifest declares its `alexa` and `http` dependencies. `iot_class` is `cloud_push` and `integration_type` is `service`.
- Changed: The access token is kept across options-only reloads.
- Fixed: A wrong client ID on the custom-endpoint path was reported on a form that has no client ID field.
- Removed: German translation.
