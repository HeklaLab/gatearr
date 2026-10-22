# Validation — Gatearr 0.3.4 — 22 October 2026

- **286 automated tests passed**, with the existing Starlette/httpx deprecation warning.
- Reviewed common interface terminology in all 21 bundled catalogs. Catalog keys and all interpolation placeholders are unchanged. Automated page checks cover every non-English language, RTL markup for Arabic/Hebrew, and persistence/priority of custom interface and email translations. This is a focused terminology review, not independent native-speaker proofreading of every catalog sentence.
- Regressions cover stale update-cache results after upgrade, semantic version equality despite a different build revision, cache invalidation, a single collapsed/open release history, and image width preservation through email save/reload and multipart rendering.
- Browser checks verified a 140 px image renders at 140 px and its preview carries the same width; Delete uses the shared danger color. Temporary email edits were discarded without saving.
- At 390 px, Updates, email editing and user permissions fit the page without horizontal overflow. Permission choices have no nested scrolling or maximum-height clipping. Only the installed release is expanded.
- Local isolated HTTP/SMTP smoke passed against simulated media and Seerr servers, including account recovery, native policy readback and editor flows. No production-server or local Docker validation is claimed.
- The existing demonstration data was preserved. The expanded 30-library fixture is confined to the local preview launcher and is not included in the release. GitHub Actions gates publication on Docker startup and HTTP/SMTP validation.

# Validation — Gatearr 0.3.3 — 22 October 2026

- **260 automated tests passed** locally on Python 3.12, with one existing Starlette/httpx deprecation warning.
- Regression checks cover typed Emby/Jellyfin policy controls, stale-write rejection, read-only refresh, group ownership and permission tabs, Seerr flags/quotas, the block email studio, branding uploads and browser titles, and public media URL migration 0019.
- Browser review covered group tab navigation, user/group admin-tools spacing, sticky Logged as banner, email drag/drop and undo, and narrow editor layouts. Native permissions were exercised using simulated APIs; no production Emby, Jellyfin or Seerr validation is claimed.
- Local isolated HTTP/SMTP smoke exercises setup, account creation/recovery, group policy write/readback and visual editors against simulated services. The smoke now checks typed controls and native policy readback instead of the removed raw-code display.
- Docker validation and AMD64/ARM64 container publication are gated by GitHub Actions. No local Docker engine is available.
- Translation structure and placeholders are tested; full native linguistic review of all supported languages is not claimed.

# Validation — Gatearr 0.3.1 — 21 October 2026

- **198 automated tests passed** for the full application suite, with one existing Starlette/httpx deprecation warning.
- Automated regressions cover explicit application selection/order across multiple full-width rows, absence of injected account/tool cards, administrator and member tool grants, safe row validation, and preservation of existing administrator grants during migration 0016.
- Password-policy coverage exercises complexity rules, optional enforcement, length bounds, CSRF/admin access and rejection before remote mutations in self-service changes, resets, administrator changes and account cloning.
- Existing authentication, reset tokens, email notifications, proxy compression/WebSocket authorization, library permissions, groups and translation regressions remain in the full suite.
- Browser checks verify that clicking Emby in the preview selects its block without navigation or a blank screen, application checkboxes/order work, and language management is compact. The demo uses simulated servers; no user's live Emby or native tool was modified.
- New interface labels in language packs fall back to editable English where translations have not yet been supplied. Fixed interface entries are separated from authored page/How to content and mail templates; stored overrides are retained.
- Full isolated HTTP/SMTP smoke passed against running Uvicorn and simulated Emby/Seerr services, including setup, cloning, library/group permissions, visual previews/publication and account recovery.
- Docker startup, health and HTTP/SMTP smoke are gated by GitHub Actions before multi-platform publication. No local Docker engine is available.

# Validation — Gatearr 0.3.0 — 20 October 2026

- **189 automated tests passed** locally on Python 3.12; one existing Starlette/httpx deprecation warning remains.
- All 21 bundled catalogs (English plus twenty additional languages) cover the same 1,162 source entries. Automated checks verify nonempty values, no unresolved translation tokens and matching placeholder counts, including default email templates.
- Visual-studio regressions cover separate home/login/footer drafts, transient previews, publication, revision conflicts, nested columns, uploaded images, sanitized rich content, sign-in-form invariants, unsafe styles/links, admin-only routes, CSRF, local-script CSP and member account-card access when an admin tool is unavailable.
- How to regressions cover nested choice snapshots, cyclic-parent rejection, rich guide steps, preview-before-publication, direct-guide entry, retained IDs and publication conflicts. Upgrade tests preserve enabled languages, names, custom translations, existing portal snapshots and encrypted connections.
- Full isolated HTTP/SMTP smoke passed against running Uvicorn instances and simulated media/services. It now exercises visual home preview/save/publish, movable login-form preview and all six PNG assets, in addition to existing setup, account recovery, clone, permissions, group, synchronization and mail flows.
- Browser checks exercise pointer dragging from the palette into the real preview and nested columns, click-to-edit, automatic draft saving, choice navigation and responsive previews. The editor runs only local scripts; public pages keep scripts disabled. Preview frames disallow scripts/forms and do not publish edits.
- No local Docker engine or user's live native service was used. GitHub Actions gates release on the full tests, actual Docker build/startup/health and HTTP/SMTP smoke, then publishes AMD64 and ARM64 images.
- Translation packs are initial machine translations with automated structural validation and editable overrides. Professional linguistic review of every string is not claimed. Uploaded assets and custom icon choices are preserved; third-party logo source URLs and checksums are recorded locally.

# Validation — Gatearr 0.2.3 — 20 October 2026

- **170 automated tests passed** locally with Python 3.12; one existing Starlette/httpx deprecation warning remains.
- Regression coverage verifies that outgoing Accept-Encoding is replaced, not duplicated, and responses preserve Content-Encoding with original streamed bytes. Real Brotli/Zstandard HTML fixtures work without optional HTTPX decoders; gzip, deflate, stacked and unknown encodings cover HTML, JavaScript and binary images.
- Existing proxy authorization, origin, redirect, credential stripping, revocation and WebSocket tests remain in the full suite. GitHub Actions gates release on the full tests and Docker startup/HTTP/SMTP smoke.
- No local Docker engine or user's native Radarr instance was used; the local upstream responses are simulated.

# Validation — Gatearr 0.2.2 — 19 October 2026

- **152 automated tests passed** locally with Python 3.12; one existing Starlette/httpx deprecation warning remains.
- Full HTTP/SMTP smoke passed with the isolated simulators: setup, import/cloning, library access, account mail/recovery, nested How to, portal publication, image upload, Seerr and group policy readback.
- New checks cover all 2,060 bundled Font Awesome Free icon/style entries and WOFF2 fonts, visual-picker controls, brand/regular rendering, safe icon identifiers, rejection of external service icon URLs, retained uploads and persistent How to icon choices.
- Tool regressions cover private root/prefixed URLs, partial disabled optional services, explicit API-key and URL Base errors, form preservation without secret disclosure, automatic configured-tool access for admins and unchanged member grants, including custom layouts without service blocks.
- Browser checks verified icon search/selection/save and the clearer navigation/control layout. GitHub Actions gates the Docker startup/health/smoke and AMD64/ARM64 release. No local Docker engine or real native tool instance was used; validate native URL Base/authentication on your server.

# Validation — Gatearr 0.2.1 — 19 October 2026

- **145 automated tests passed** locally with Python 3.12; one existing Starlette/httpx deprecation warning remains.
- New regressions verify dark-only defaults and old preset normalization, active Services/How to navigation, hidden single-language controls, footer column visibility and preservation, sanitized inline PNG/SVG upload, readable user-name audit history and secret redaction.
- Path-based tool tests cover the Gatearr wrapper, prefixed HTML/assets, absolute and relative redirects, credential stripping, live-session revocation, origin checks and WebSockets. Native tools must be configured with the documented URL Base. They share the portal origin; this is explicitly documented and limited to trusted applications.
- Full isolated HTTP/SMTP smoke and browser checks cover the updated flow. Docker build/startup/health/smoke and AMD64/ARM64 publication are gated by GitHub Actions; the local workspace has no Docker engine.
- Actual native Emby/Jellyfin/Seerr/Radarr/Sonarr/Bazarr deployments and the user's proxy were not used in these checks. Validate native URL Base and proxy-authentication settings on the test server before production rollout.

# Validation — Gatearr 0.2.0 — 19 October 2026

- **140 automated tests passed** with Python 3.12. One existing Starlette/httpx test-client deprecation warning remains.
- An isolated full HTTP/SMTP smoke passed: setup, import, cloning, library assignment, account verification/recovery, password changes, translation, menus/How to, footer, Seerr synchronization and group policy readback.
- New coverage includes upgrade from migration 0012 to 0013 without losing accounts or encrypted connections, removal of retired Tracearr data, setup error repopulation without API-key disclosure, editable themes and enforced preferences, rich-footer sanitization, SVG validation, member-session assistance, notification delivery, tool permissions, one-time tickets, origin validation, HTTP proxy header isolation, WebSockets and immediate revocation.
- Browser inspection verified grouped administration, dark theme with transparent logo, equal-width palette fields, rich footer controls and the full user page.
- No local Docker engine is available. GitHub Actions gates publication on the actual Docker build/startup, health checks and HTTP/SMTP smoke, then builds Linux AMD64 and ARM64 images. See the version's workflow for the container result.
- Native Emby/Jellyfin/Seerr/Radarr/Sonarr/Bazarr instances and a real external reverse proxy were not used in these local checks. Tool proxy routes use mock upstreams, including a WebSocket exchange. Follow the documented dedicated-host and private-upstream prerequisites and validate against your installed versions.

## Historical validation records

The following records describe older versions, including integrations retired in 0.2.0.

# Validation — 19 October 2026

- **127 automated tests passed** locally, including footer publication/validation, default journeys, release version checks and failed-network handling, policy merge/individual overrides/readback/drift, group removal, sensitive permissions, and Seerr handoff identity/origin/expiry/replay protection.
- Full isolated HTTP/SMTP smoke passed with the included media/service simulators: existing authentication, account recovery, cloning, library access, mail, translation and service synchronization, plus version page, default guides, footer publication and queued group policy readback.
- Browser inspection verified the fresh default blue/cyan theme and logo without an added background, the footer editor and per-permission confirmation indicators.
- No local Docker engine is available. The actual Docker build/smoke and AMD64/ARM64 image publication are gated by GitHub Actions. This document records local checks; the release workflow provides the container validation result.
- Native Emby/Jellyfin/Seerr instances and a real reverse proxy were not used for these new tests. Validate policy availability and automatic Seerr login against the deployed versions. Existing server-owned/authentication fields remain read-only; unsupported policy fields are not invented.

## Earlier regression evidence

# Validation — 16 October 2026

## Executed checks

- **103 tests passed** with Python 3.12 and the pinned dependencies. One Starlette/httpx test-client deprecation warning remains.
- Fresh database through migration `0010`: English is the only language and there is only one user locale column. A prepopulated upgrade preserves media accounts, roles, encrypted connections and email addresses; removes the previously supplied French language; and falls back to English for affected users.
- Upgrade bootstrap preserves the original encryption key, copies a single existing portal SQLite database to the new standard path and refuses to guess between multiple databases.
- Setup requires an explicit server API key, rejects invalid connection proof and uses a browser-bound, expiring capability for the first-admin selection. No installation token or media API environment fallback exists. Concurrent/repeated first-admin claims, wrong identity/password, expired capability, disabled accounts and last-admin removal are covered.
- Separate administration sections, prominent back links, completed-wizard hiding/redirect, draft/published button-hover colors, language consistency, all-string translation page, configured-service-only user indicators and cached/sanitized authenticated connection health are covered.
- Emby library regression: virtual-folder GUIDs deliberately differ from numeric item IDs. Permission writes use the GUIDs, clear obsolete exclusions, preserve unrelated restrictions and verify readback. Jellyfin has its own contract tests.
- Seerr language changes preserve unrelated settings, queue through the existing synchronization worker and are verified after writing. The same user preference selects Gatearr email language.
- Existing authentication, CSRF/origin validation, rate limits, session rotation/revocation, reset expiry/replay/concurrency, encrypted SMTP queue, email verification, HTML sanitization, PNG validation, user cloning, nested journeys, portal publication and synchronization regressions pass.
- Full HTTP/SMTP smoke on an isolated new database: setup without token/environment API key, user import, native cloning, one-library assignment, home preferences, English block builder, nested device journeys, PNG icons, verified email, subscriptions, password change/reset, replay rejection and email propagation to both service simulators passed.
- Primary local demo upgraded to `0010`; existing media accounts/configuration retained. Browser inspection confirmed English-only initial language selection, separate dashboard sections, visible back buttons, green connection indicators with check details, the hover color field and 761 translatable interface/content/email entries on one page for this demo's content. A separate fresh instance showed the six-step breadcrumb and explicit API-key input without a setup token.
- `compose.yaml` and `compose.demo.yaml` validate against the official Compose Specification JSON schema.
- Repository scan found no occurrence of the previous project name in shipped source text. `.env`, databases, caches, generated secret files and local backups are excluded from the packaged source/build context as appropriate.

## External API evidence and limits

The [Emby virtual-folder contract](https://betadev.emby.media/reference/RestAPI/LibraryStructureService/getLibraryVirtualfoldersQuery.html) exposes both navigation IDs and `Guid`; Emby's permission model uses folder GUIDs. The [Seerr settings route](https://github.com/seerr-team/seerr/blob/develop/server/routes/user/usersettings.ts) supports writing and reading account `locale` while preserving unrelated fields.

Tracearr's current [identity schema](https://github.com/connorgallopo/Tracearr/blob/main/packages/shared/src/schemas.ts) has no writable locale. Its [language implementation](https://github.com/connorgallopo/Tracearr/blob/main/packages/translations/src/language.ts) reads client storage and browser/device settings. **Gatearr cannot synchronize Tracearr interface language through this API.** Contact email/newsletter synchronization remains supported and is verified separately. No success state is fabricated for language synchronization. Tracearr's internal write API can change between versions.

The release has not been built/run locally inside Docker because no Docker engine is available in this workspace. The repository contains CI Docker build/smoke steps; a successful build of the earlier release was supplied by the user from Windows. The executed integration tests use the included simulators and HTTP mock transports, not the user's Windows Emby, Seerr or Tracearr instances. The corrected GUID mapping still needs a live single-library check on that Emby server.

Setup must remain private until completed. Without an installation token, an unconfigured public portal cannot determine its owner solely from an arbitrary visitor's chosen media-server URL/key. CSRF, rate limits and first-admin password proof remain active.
