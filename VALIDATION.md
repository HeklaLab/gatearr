## Container distribution preparation

- Official supplied PNG copied unchanged and used as the default Gatearr branding; custom names and logos retain their own branding.
- 103 tests passed locally after integration. Deployment/source/demo Compose files pass Compose JSON schema validation.
- GitHub Actions gates multiarchitecture container publication on the tests and Docker/SMTP smoke. Docker execution and GHCR publication must be confirmed by the actual workflow before claiming this release is available.

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

The new release has not been built/run locally inside Docker because no Docker engine is available in this workspace. The repository contains CI Docker build/smoke steps; a successful build of the earlier release was supplied by the user from Windows. The executed integration tests use the included simulators and HTTP mock transports, not the user's Windows Emby, Seerr or Tracearr instances. The corrected GUID mapping still needs a live single-library check on that Emby server.

Setup must remain private until completed. Without an installation token, an unconfigured public portal cannot determine its owner solely from an arbitrary visitor's chosen media-server URL/key. CSRF, rate limits and first-admin password proof remain active.
