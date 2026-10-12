# Changelog

## 0.5.0

### Added
- Reconfigure flow: change the event gateway or credentials without removing
  the integration (removing it makes Alexa forget every device).
- Entities: "Alexa linked" and "Sync status" diagnostic sensors, and a
  "Resync with Alexa" button that resends every exposed entity.
- Repair issue when an exposed entity no longer exists, with a one-click fix.
- Renaming an exposed entity ID in Home Assistant now carries over its
  exposure and Alexa name instead of silently dropping it.
- The naming step shows each entity's friendly name and area.

### Changed
- The sync state is persisted. A restart no longer resends everything, and
  removals made while the skill was not linked are no longer forgotten.
- Entities are pushed to Alexa automatically once account linking completes.
- Alexa names must be unique, ignoring case. Overlapping names such as
  "Lamp" and "Floor Lamp" are fine. An entity's Home Assistant name counts
  when it has no custom name.
- Locale is `en-US` (previously `de-DE`). German translation removed.
- Manifest declares its `alexa` and `http` dependencies; `iot_class` is
  `cloud_push` and `integration_type` is `service`.
- The access token is kept across options-only reloads.

### Fixed
- A wrong client ID on the custom-endpoint path was reported on a form that
  has no client ID field.
