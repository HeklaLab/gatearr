# Validation — Gatearr 0.4.0 — 23 October 2026

## Publication review — 23 October 2026

- **380 automated tests passed** on Python 3.12; one existing Starlette/httpx deprecation warning. Coverage includes authentication/recovery, native revocation, CSRF/origin checks, proxy traversal/authorization, image limits, private photos, dependency-gated widgets/mail, group lifecycle and session-bound group review with drift/expiry/tamper rejection.
- A new isolated real HTTP/SMTP smoke passed: five-stage setup, native picture upload/readback/cache invalidation, account cloning, group permission preview/confirmation and native readback, page/guide/email editors, verification, password change/recovery and Seerr propagation. Upstream services were simulators.
- 51 page-width checks covered the portal, account, admin mosaic, identity, builder, integrations, email tabs, themes, groups, user detail, Captcha, languages and updates at 1280, 768, 390 and 320 px. No global horizontal overflow or console warnings/errors appeared in these checks. Screenshots were renewed from the running application, with fictional accounts and local addresses; existing v0.3.2 images remain historical assets.
- Browser follow-up caught and fixed a Jellyfin placeholder reverting after dynamic language changes and a malformed preset-logo preview. Rechecked Jellyfin plus French/German/English switching, selected-preset preservation, the five-step mobile layout and stacked mobile group comparisons. No permission changes were confirmed during browser inspection.
- Python pinned runtime audit: no known vulnerabilities and no skipped package entries. OSV returned no known advisories for the four bundled CAPTCHA npm packages at the review time. This does not cover unknown vulnerabilities, container/base-OS packages or upstream native applications.
- Source review rechecked session rotation, hashed identifiers, CSRF/origin validation, live administrator checks, scoped statistics, safe uploads, native credential forwarding and container hardening configuration. See SECURITY_REVIEW.md for residual deployment risks.
- No local Docker engine or live production Emby/Jellyfin/Seerr/Tracearr deployment was available. GitHub Actions must pass the actual Docker Compose build/health/HTTP-SMTP checks before image/release publication. The test suite does not establish a guarantee of zero vulnerabilities.

## Earlier interface follow-up

- **365 automated tests passed**, one existing Starlette/httpx warning. Ten initial regressions plus two additional failure-path cases cover fresh conditional defaults/non-overwrite, Emby and Jellyfin image API paths/base64/headers, private avatar access, native tag/removal invalidation, email-only dependencies, group rename conflicts, two-factor destructive confirmation, administrator guards, linked API preflight and partial native deletion retention.
- The complete isolated HTTP/SMTP smoke passed. It now includes Gatearr-to-native photo upload, native readback, a direct native photo change, synchronization and invalidated Gatearr image URLs, as well as account cloning, groups/library permissions, editors, verified email, password changes/recovery and Seerr propagation. All upstream services in this run were simulators.
- Browser review completed all five dynamic setup stages in French. Language switching preserved entered API URL/key; a wrong native password displayed beside the buttons without clearing the form. Seerr testing showed server green/API red for a rejected key, then both green with the accepted key. SMTP connectivity and validation were checked. Finishing created media/Seerr cards, their aligned widgets and a full-width account card.
- The capsule navigation, dropdown and portal were visually reviewed at 1280, 768 and 320 px; the navigation stays on one line at tablet/mobile widths and the document has no horizontal overflow at those tested widths. CSS colors remain independent of geometry. The local user demo is reloaded with its saved accounts and designs preserved.
- Native JPEG/PNG profiles are validated and bounded; Jellyfin upload routing is covered with an HTTP mock transport. No real upstream deployment or Docker engine was exercised. Natural wording was revised in the bundled catalogs and placeholder/catalog consistency checked; this is not independent native-speaker proofreading of all 21 languages.
- No GitHub publication was performed by this follow-up.

## Earlier 0.4.0 validation


- Public-exposure security pass: 20 new regressions cover blank/passwordless native authentication, immediate administrator revocation and native outage refusal, native administrator URL-token suppression, encoded HTTP/WebSocket path checks, tool-proxy revocation, assistance proxy isolation, native/portal role separation and recovery-token referrers. The complete suite reports 353 passed, one existing warning.
- After updating Certifi to 2026.10.19, pip-audit reports no known vulnerabilities across all 32 pinned runtime packages, with none skipped. OSV returns no known advisories for the four bundled npm packages at the audit time. These checks exclude unscanned container/OS packages.
- Isolated HTTP/SMTP smoke passed after hardening. The user demo was reloaded with its four users and existing configuration retained; health/login respond 200. The review and residual public-deployment risks are documented in [SECURITY_REVIEW.md](SECURITY_REVIEW.md). No security correction was published or deployed to a production server.

- **353 automated tests passed**, with one existing Starlette/httpx deprecation warning. Coverage includes six theme palettes, policy and draft revision checks; widget audience selection and priority; native library privacy and user-scoped counts without a library selector; Tracearr stable identity, pagination and rejection of cross-user/server data; current native disabled-account checks before cached statistics; request/season baselines, deduplication, independent dependency failures and mail cancellation after consent or integration changes.
- Real headless Chrome completed Cap's HashWX and instrumentation challenge using local widget/WASM assets. The resulting token was rejected on the wrong form (400), accepted once on password recovery (200) and rejected on replay (400). The instrumentation frame is isolated; the login/recovery parent keeps JavaScript unsafe-eval disabled. No cloud assets or captcha dashboard are used.
- Asset-policy regressions cover a valid PNG larger than 2 MiB, rejection above 5 MiB, remote-image refusal, server-specific widget logos and Tracearr mail dependency checks through legacy endpoints. Browser checks confirmed aligned email-template actions, a compact appearance-policy row, disabled widget entries and a successful large-logo upload and email-image upload.
- Additional browser checks verified three nested widgets match application-card widths at 1280, 768, 390 and 320 px, with no horizontal overflow. Presets, connection saves/tests, successive email saves and translation resets update without page navigation. Missing captcha prevents the browser submission without clearing credentials; its local SVG checkmark was rendered after a real challenge.
- Browser checks cover Applications & API, themes, Captcha settings and the portal builder at 1280, 768, 390 and 320 px without horizontal page overflow. Palette and connection screens were rendered for visual review. API tests cover private widget output and native-interface authorization. Real native iframe policies remain deployment-dependent.
- Full isolated HTTP/SMTP smoke passed through setup, native account cloning, library/group permission readback, visual editors, uploads, verified email, password changes/recovery and Seerr propagation. Test service responses are simulated. Tracearr contracts were checked against its public v2 source, including bitrate in kbps; traffic remains an estimate based on recorded sessions.
- The existing local demonstration was backed up before migration 0020 and reloaded without resetting its accounts, integrations or 30-library fixture. Fictional libraries and demo services remain outside the shipped repository.
- All 21 catalogs retain matching source keys and interpolation placeholders. New-season mail defaults are localized in all bundled languages. Core wording was reviewed; exhaustive native-speaker proofreading of every sentence is not claimed.
- No local Docker engine is available, so Docker build/startup and live native-server validation are **not** claimed. The Node runtime image tag was checked for Linux AMD64/ARM64; the existing GitHub workflow still gates future publication on tests, Docker startup and HTTP/SMTP smoke. Nothing was published during this development pass.

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

## 0.4.0 interface follow-up — 2026-10-23

- Anonymous header now uses the approved capsule navigation and a compact language menu.
- Branding logo upload, explanatory text, removal checkbox and identity fields have explicit spacing.
- Group settings are compact and appear above permissions; members appear below permissions. Existing rename/deletion safeguards are retained.
- Email templates and SMTP settings have separate tabs; SMTP saves and diagnostics return to the SMTP tab.
- Full regression suite: **365 passed, 1 existing deprecation warning**. Browser checks used an isolated simulator-backed demo, including 320px group/branding layouts with no document overflow. Main demo data and CAPTCHA settings were preserved.
- Two admin-home mockups were prepared separately; the production admin landing page was not redesigned in this follow-up.

## 0.4.0 approved Mosaic home and capsule navigation — 2026-10-23

- Replaced the admin landing with the approved Mosaic layout: six compact section links and a separate updates strip, using existing localized labels and theme colors.
- Added a measured, sliding capsule selection. The live capsule remains connected while the destination content is replaced, so the transition survives fast responses.
- Capsule links between Home, My account and Administration now fetch authenticated, uncached HTML and replace content without a document reload. History, focus, body layout, footer, account menu and CSRF form fields are updated; expired sessions use normal sign-in navigation. Other application links retain their normal navigation and page-specific script initialization.
- No HTML response scripts are evaluated. Requests stay on the same origin and rapid navigation cancels superseded requests. Reduced-motion preferences disable the sliding animation.
- Full suite: **365 passed** (one existing deprecation warning); final focused portal/security/profile checks: **47 passed**. Browser verification covered the three destinations, browser back/forward, account controls, theme switching after navigation, retained capsule DOM, and a 320px viewport without document overflow.
- Demo data, service configuration and main-demo CAPTCHA settings were preserved. No GitHub publication was performed.

## 0.4.0 consistent admin section labels — 2026-10-23

- All administration section and editor headings now share one localized `Administration · Section` label, including pages that previously omitted it.
- One shared style controls accent color, typography, uppercase presentation and spacing; visual builders no longer use a separate cyan override for these labels. Public portal content is unchanged.
- 47 targeted regression tests passed with the existing deprecation warning. Browser checks confirmed the email and portal-builder headings use the shared presentation.

## 0.4.0 theme-matched default logos — 2026-10-23

- Blue Boréal, Electric Lime and Neon Rose now select their bundled default logo automatically. Dark mode uses a light wordmark with a colored symbol; light mode retains the original dark wordmark and colored details. Auto mode follows the appearance policy.
- Header, branding preview, portal logo blocks and initial setup share the default-logo behavior. Applying a theme draft updates the editor immediately; public pages use the published preset. Navigation away from a draft restores the published identity.
- Uploaded custom logos retain priority and are not filtered or replaced by theme selection. Initial-setup upload previews also retain priority over preset selection.
- The local bundled-image allowlist accepts only the three known logo PNG paths, with no general filesystem or remote-image allowance.
- Full regression suite: **367 passed**, one existing deprecation warning. Added regression coverage for draft/public separation, publication, custom upload precedence and exact bundled-image allowlisting. Browser verification covered both new presets in light and dark modes and immediate draft switching without page reload.

## 0.4.0 interface refinement — 2026-10-23

- Portal-builder color controls now use labeled swatch rows with visible hex values, grouped by button/background settings. Gradient controls are collapsed when unused.
- Tracearr activity widgets display the selected calendar/rolling period and UTC date range. Calendar rollover invalidates aggregate caches; previews show the same period metadata. The actual query bounds and displayed dates are checked for week, month and rolling 30-day periods.
- Preset colors and default logo preview update on click before the asynchronous draft save finishes; save failures restore the last saved preview.
- Account appearance settings are available from the header only; the duplicate account card was removed. The default English profile heading is now “Profile picture.”
- Integration detail summaries use a shared status column. Browser measurements confirmed identical dot positions across all seven services.
- Existing regression suite: 367 passed, one existing deprecation warning. Three additional period checks passed as part of 44 targeted widget checks. Browser verification covered color layout, account fields, immediate logo preview and integration status alignment.
- A separate interactive proposal was prepared for language management with flags; the current translation-center page was not replaced.
