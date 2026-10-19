# 0.2.1 — 2026-10-19

- Dark-only appearance with a darker, subtle background gradient and editable colors.
- Clear active parent/child administration navigation and consistent button spacing.
- Radarr, Sonarr and Bazarr embedded under /tools on the portal hostname, with per-request permissions.
- Footer editor shows only the selected columns, with rich text and inline PNG/SVG uploads; hidden drafts are retained.
- Hide the language selector when only one language is enabled.
- Readable audit actions, username snapshots and redacted change details.

# Changes

## 0.2.0 — 2026-10-19

- Grouped administration, intuitive service creation and How to editing.
- Retired Tracearr integration and removed its saved credentials/jobs/preferences.
- Audited, expiring user assistance using live member sessions.
- Optional Radarr/Sonarr/Bazarr origin-isolated proxies and individual user grants.
- Direct administrative account changes and encrypted localized notifications.
- Editable light/dark themes, gradients and appearance policy.
- Centered rich footer columns, sanitized SVG and bundled Font Awesome.
- Consistent controls, account service card and preserved setup fields.
- Storage preflight and explicit installation prerequisites.


## 0.1.0 — 2026-10-19

- First public multiarchitecture Docker release, refreshed once at the owner's request.
- Installed version/build, admin changelog and GitHub update indicator.
- Global footer builder with text, links, PNG logos and draft previews.
- Editable Windows/Mac/Android/iPhone guides and default Seerr journey.
- Transparent logo styling and matching blue/cyan default theme.
- Complete media policy editor, per-field readback indicators and shared user groups/libraries.
- Optional Seerr automatic session handoff through the existing reverse proxy, with expiring single-use tickets.


## 2026-10-16 — Unified Gatearr portal

- English is the only bundled language. Additional languages and all text are managed on one translation page per language.
- Media API keys are required in the setup wizard and stored encrypted; removed environment-based API configuration and installation tokens.
- Gatearr naming throughout the source, containers, database and cookies. Upgrade instructions preserve existing data volumes and encryption keys.
- Numbered setup breadcrumbs. Completed installations use API connections instead of a persistent wizard entry.
- Separate Branding, Emails, Services and Users pages, plus consistent prominent back buttons throughout administration.
- Cached authenticated connection health, green/red indicators, keyboard-accessible hover details and manual refresh.
- Customizable button hover color, including draft and published themes.
- Per-user Seerr/Tracearr status indicators only when the relevant connector is configured and enabled.
- One account language for the interface, email delivery and Seerr settings, with retry/verification. Tracearr's client-only language limitation is stated explicitly.
- Emby library permissions use virtual-folder GUIDs rather than numeric navigation IDs, preserve unrelated policy and verify the write.
- Existing features retained: PNG uploads, WYSIWYG mail, nested device guides, portal blocks, secure email verification/reset, roles and media user cloning.
