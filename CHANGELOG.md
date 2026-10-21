# Gatearr 0.3.2

- Sign in with a username or the account email, verifying the same native media identity.

- Username editing updates the media login and queues verified Seerr display-name synchronization, with retries on failure.
- Application counts cap each row, preserve older selections across rows, and keep configured applications visible in the builder preview.
- Content reset retains legacy public application URLs; save confirmations use a contrasting green badge.

- Review fixes: clean group layouts, request quotas per user/group, optional Seerr counters and readable activity messages.
- Dedicated Access guide tab, easier page selection, pixel-sized spacing blocks and save feedback.
- Bundled application PNGs, complete desktop/mobile/TV starter guides, Seerr direct-link defaults and an explicit content reset preserving server connections.

- Access guides and safe editing of saved portal blocks without opening application links.
- One Applications & API card per application, refreshed administration navigation and live theme previews.
- Compact user tabs, single-group permission ownership, Seerr permissions and request summaries.
- Account deactivation rotates remote passwords, blocks Gatearr recovery and preserves the disabled state during imports. Reactivation allows password recovery.
- Choose the default language during setup. English can be disabled; at least one language must remain active.

# Gatearr 0.3.1

- Applications & API combines application links and server connections in one administration page.
- Application rows have selectable applications, column counts and drag ordering; My account is an explicit application.
- Portal builder owns How to editing; native tools require explicit per-user access.
- Compact Translations / Labels, clearer administration navigation and configurable password complexity.
- Taller tool frames, cleaner account settings, GitHub feedback links and installation guidance.

Existing data is preserved. Review your application rows in Portal builder after upgrading. See UPGRADING.md for migration behavior.

# 0.3.0 — 2026-10-20

- One visual studio for the public sign-in page, member home and shared footer, with pointer/touch drag-and-drop, real live previews, responsive widths, nested columns, rich text and image uploads.
- Edit page and block colors, gradients, buttons and hover states directly in the studio. Move the sign-in form without removing it, use starter templates, undo/redo, autosaved drafts and explicit publication with conflict detection.
- Replace How to forms with a visual choice tree, breadcrumbs and drag-and-drop cards. Choose direct links, more choices or a guide; write and reorder rich guide steps with uploaded images, download buttons and reusable server variables.
- Keep My account after applications and enabled admin tools. Bundle original PNG logos for Emby, Jellyfin, Seerr, Radarr, Sonarr and Bazarr while preserving custom icon choices.
- Include twenty additional editable language packs, with interface, default email and starter-guide translations; English alone is enabled on a fresh installation. Existing enabled languages and overrides are preserved.
- Place authenticated connection summaries for configured services above the forms, align Emby/Jellyfin and Seerr side by side and remove translation settings from API connections.
- Preserve existing layouts, guide IDs, published snapshots, accounts, uploaded assets, encrypted connections and the compressed-response proxy fix from 0.2.3.

# 0.2.3 — 2026-10-20

- Fix unreadable Radarr, Sonarr and Bazarr pages caused by compressed upstream responses: preserve wire bytes and Content-Encoding together.
- Replace the browser Accept-Encoding header instead of combining it with identity; preserve streamed HTML, scripts and images without optional server-side decompressors.

# 0.2.2 — 2026-10-19

- Increase button and navigation contrast and align service fields and user invitation controls.
- Replace text-only icon lists with a searchable visual picker for all 2,060 bundled Font Awesome Free 6.7.2 icons, including Solid, Regular and Brands.
- Remove external icon URL input from services and How to choices; keep PNG/SVG uploads and validated Font Awesome selections.
- Fix tool connection diagnostics, accept private root or prefixed URLs and ignore incomplete disabled optional tools. Preserve safe form fields on error without exposing API keys.
- Show every enabled Radarr, Sonarr and Bazarr application to Gatearr administrators automatically, including custom portals without service blocks. Member tool grants remain independent.

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
