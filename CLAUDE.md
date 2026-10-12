# Alexa Smart Home Manager

Home Assistant custom integration (HACS). It replaces the YAML-only
`alexa: smart_home:` setup with a config entry, so exposed entities and Alexa
names are managed in the UI and pushed to Alexa without a restart.

Display name: **Alexa Smart Home Manager**. The domain stays
`alexa_bridge_manager` and must never change, because it is part of every
user's entity IDs, settings and stored data.

## Layout

- `custom_components/alexa_bridge_manager/` - the integration
- `tests/` - pytest, uses `pytest-homeassistant-custom-component`
- `images/` - screenshots used by the README
- `.github/workflows/` - hassfest, HACS validation, pytest

## Tests

```bash
pip install -r requirements_test.txt
python -m pytest tests/ -q
```

On Linux the `libturbojpeg0` system package is also needed (Home Assistant's
`alexa` component imports `camera`). Run the tests before every commit.

## Code rules

- `strings.json` and `translations/en.json` must be identical. English is the
  only language.
- Names must be unique only when identical, ignoring case and spacing. Never
  block merely similar or overlapping names.
- Never publish a real client ID, client secret or token: not in code, tests,
  screenshots, logs or docs. Test fixtures build credentials from the prefix
  constants.

## README

The README describes the current state only and is always kept clean:

- No version history, "new in", "previously" or "now also" wording. That is
  what the changelog is for.
- Plain, factual English. No marketing phrases or filler.
- Update it in the same change whenever behaviour, setup steps, entities or
  limitations change.
- Screenshots live in `images/` with relative links. Check each one for
  personal data before adding it.

## Release notes

Every release has an entry in `CHANGELOG.md`. HACS shows the GitHub release
body in Home Assistant, so that is what users read when they update. Write it
for them, not for developers.

Format, one line per change, newest version first:

```
## 0.6.0

- New: ...
- Changed: ...
- Fixed: ...
- Removed: ...
```

- Only these four prefixes, in this order: `New:`, `Changed:`, `Fixed:`,
  `Removed:`. Leave out prefixes with no entries.
- One sentence per line, user-visible effect first. No commit hashes or
  internal refactoring details.
- Mention anything users must do (for example "restart Home Assistant", or
  "re-link the skill in the Alexa app").

## Release checklist

1. Tests pass (see above) and CI on `main` is green (hassfest, HACS, pytest).
2. Bump `version` in `custom_components/alexa_bridge_manager/manifest.json`.
3. Add the version's section to `CHANGELOG.md` in the format above.
4. Check that the README still matches the behaviour.
5. Commit and push to `main`.
6. Tag `vX.Y.Z` (matching the manifest version) and create the GitHub release
   with only that version's changelog lines as the body:
   ```bash
   git tag vX.Y.Z && git push origin vX.Y.Z
   gh release create vX.Y.Z --title "vX.Y.Z" --notes-file <file with that section's lines>
   ```
7. Pushing, tagging and publishing a release are outward-facing. Do them only
   when the user asks.
