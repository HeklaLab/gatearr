# Gatearr 0.4.1 implementation and review

The user approved the sidebar, capsule tabs and structured profile. This document records implementation details and validation boundaries for 0.4.1.

## Connections and permissions

Connection tests use entered values without saving them or replacing the status of the saved configuration. Empty credentials reuse the saved secret. Edits invalidate transient results. Server reachability and API authentication remain distinct.

Radarr/Sonarr/Bazarr require their native URL Base `/tools/SERVICE/app`. A valid root API with a missing URL Base produces a specific diagnostic. Where supported, permit the exact upstream hostname, rather than disabling host restrictions. Bind addresses and allowed hosts are different settings.

Tdarr uses the configured WebUI address (usually port 8265), through the session-protected `/tools/tdarr/app/tdarr/` path. The final `tdarr/` supports Tdarr's base-path discovery. Gatearr strips this prefix for HTTP and WebSocket requests. Native authentication is retained; Gatearr cookies and keys are never forwarded. Service cookies use a dedicated namespace and the Tdarr path, cannot overwrite Gatearr cookies, and are decoded only when reaching Tdarr. Other reverse-proxy cookies are not forwarded. This remains interface access only. Actual compatibility must be verified against the user's Tdarr version and reverse proxy.

Official base-path documentation: https://docs.tdarr.io/docs/installation/extra/

New tool grants require a configured integration. Existing grants survive disablement; actual access still enforces service configuration, native account revocation, explicit grants and administrator restrictions where applicable.

## Personalization compatibility

Public interface keys are explicitly cataloged in `app/public_interface_keys.json`. Native admin translations ignore overrides. Old admin overrides stay stored but are no longer applied or editable. The public navigation uses a separate translator even on admin pages. Public authored content stays editable; admin-only blocks, tool subtitles and permission labels are excluded.

Identity no longer edits login text. The login builder reads the legacy setting when no custom layout exists and retains legacy translations through a compatibility fallback. Existing custom login layouts are untouched.

Email editors only offer active languages; disabled translations stay stored. The invitation introduces the common portal, shared media credentials, recovery and device guides. An unchanged legacy factory body upgrades at read time, while custom bodies and HTML remain intact.

Language changes in assistance mode are presentation-only and do not change the assisted account. Other write restrictions remain active.

## Verification boundaries

Automated tests use simulated native services. Browser QA uses the local fictional-account demo. Neither proves behavior on the user's production media services. The user's live Tdarr/frame failure must be retested after installation; no cause is claimed solely from the original screenshot.

Release validation: 403 tests passed, one optional theme export skipped, with an existing Starlette/httpx deprecation warning. French language switching and 390px layout were checked in the browser. Some new technical admin help strings still use English fallback outside French.


## Latest demo refinement

All local tab strips (including the nested builder page selector) now share the header capsule colors and sliding marker. The sidebar is permanently open and has one Administration link. Tab GET navigation swaps content without a document reload; page-specific scripts load in order, global page handlers use an abortable lifecycle, permission polling is cleaned up on exit, and builder drafts finish saving before navigation. Group tabs retain their current form locally.

The logo preparation dialog accepts browser-readable PNG/SVG/JPEG/WebP within 5 MiB / 40 megapixels, preserves proportions by default, offers original / 3:1 / square framing, zoom and pointer/keyboard panning, then produces a bounded PNG before form submission. Existing server validation remains unchanged. A browser upload of the bundled 2172×724 logo was saved as a validated 1024×341 PNG. The test's custom logo was then removed from configuration to restore automatic theme branding; its asset remains stored.

The full 397-test suite passes after these changes. Manual browser checks cover dynamic tabs (including builder initialization and history), immediate user filtering and a narrow viewport without horizontal overflow. New crop dialog copy currently has French/English variants; other languages use English fallback.


## Structured profile integrated in the functional demo

The approved Structured profile now replaces the staggered account card grid. Identity, password, preferences (including library controls) and linked accounts share one aligned sheet. Profile photo editing is progressively disclosed and retains the existing upload endpoint and validation. Separate username, email and password actions remain separate forms; no new cross-service transaction is introduced.

User and group permission categories are native full-width accordions. Their underlying controls, form versions, group review, permissions inheritance and destructive confirmations remain intact. Required-field validation opens enclosing accordions before focus. Seerr categories share the same organization; group members remain at the bottom. The account-menu language field fills the row and auto-submits on change; the native submit button remains available without JavaScript. French selection and restoration to English were verified through the live menu without HTTP 403.

Full regression suite: 403 passed, one optional theme-export test skipped. Browser verification uses the live demo rather than the graphical mockup.
