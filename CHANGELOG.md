# 0.4.4 — 27 October 2026

## Improvements

- Upload separate light and dark logos; existing single logos remain compatible.
- Choose light, dark or automatic appearance before signing in when the administrator permits it.
- Add smooth, accessible transitions to device choices and guides.
- Group changelog highlights by topic in compact independent columns.
- Review interface wording and fill missing translations across all 21 bundled language packs.

## Fixes

- Accept email templates up to 50,000 characters, retain sanitization and explain oversized input; improve subject/editor spacing.
- Keep group Seerr permission switches compact and aligned.
- Show unavailable embedded-tool access with an explanation while retaining direct links.
- Allow disabling an offline integration without revalidating its saved settings.

# 0.4.3 — 26 October 2026

## Improvements

- Choose opening behavior per application card: direct link, embedded tool or media guide. Unconfigured tools offer a direct URL field.
- Size images in pixels or percent; resize/crop large uploads and see saved-image previews.
- Group release history by series and add a GitHub roadmap shortcut.
- Refresh guide cards, simplify guide editing and unify builder navigation. Keep templates exclusive to Portal; add My account background artwork.

## Fixes

- Keep same-named custom applications editable and independent; isolate each card’s destination and draft changes (#4, #6).
- Correct image alignment, responsive sizing and empty placeholders (#8).
- Fix Tdarr resources with hash-based URLs and improve connection guidance.
- Preserve media ports/paths and safely fall back to the public Emby interface when automatic sign-in is unavailable.
- Restore theme persistence, spacing and color-control alignment; remove duplicate widget titles. Place Library updates and Statistics last, preserving the Tracearr logo.

The deployment-specific Emby port report (#5) still needs confirmation from the reporter. Music support remains on the roadmap without an ETA.

# 0.4.2 — 25 October 2026

## Interface and navigation

- Refresh the portal and administration with a shared diffuse landscape, palette-derived glass surfaces, consistent rounded controls and animated ON/OFF switches. Improve contrast and responsive layouts across Blue Boréal, Electric Lime and Neon Rose in light and dark appearances.
- Reorganize the administration landing page into a compact card directory. Smooth sidebar selection and submenu expansion without stretched panels or page jumps; preserve the header and keyboard focus during dynamic navigation.
- Simplify the account menu onto one glass surface, distinguish the active language from a subtle hover state, and reuse the existing muted red for Sign out.
- Save supported preferences dynamically with animated feedback and preserved scroll, including subtitle choices and Bazarr configuration.

## Portal and builders

- Integrate Emby/Jellyfin library counts and Seerr request quotas directly into their application cards, replacing the two standalone widgets. Portal builder offers optional card information, enabled in default presets, while retaining existing settings and audiences.
- Make application purposes clearer: Access media and Request new movies & series appear below application names, before statistics. Large cropped service artwork adds depth without hiding content.
- Offer exact or promotional media counts, rounded down to tens or hundreds, including optional episode counts. Explain Seerr quotas with real periods, limits, remaining counts and aligned progress bars, including unlimited/unavailable states.
- Fix Portal builder layouts after dynamic navigation by preserving stylesheet order. Adapt tools and editing panels to the builder's available width, keep labels readable, and group application switches and reorder controls consistently.
- Add matching Choose another device buttons above and below every access guide.

## Bazarr subtitle preferences

- Let authorized users select subtitle languages from My account for one administrator-selected shared Bazarr language profile. This permission is independent of access to the Bazarr interface and is available only after complete integration setup.
- Set individual or group language limits, with a selected/allowed counter and add/remove controls. Already-configured languages remain selectable and count toward personal capacity without duplicate profile updates or warnings.
- Choose free replacement, a configurable lock in days, or an indefinite lock with administrative unlocking. Enforce locks on the server. Removing a personal choice does not remove shared Bazarr languages or downloaded subtitles; availability still depends on each library title.
- Preserve existing profile options and languages, detect concurrent changes, and verify the native API readback.

## Administration and fixes

- Add administrator-only SMTP history under Activity log, with shortcuts at the bottom of Emails and the mail editor. Record recipient, subject, purpose, SMTP acceptance and safe failure details without retaining message bodies, private links or SMTP credentials. SMTP acceptance does not prove delivery to the recipient's inbox.
- Manage language by user or group, falling back to Gatearr's default when a group has no active language. Apply the effective language to the interface, emails and Seerr synchronization without overwriting personal preferences.
- Refresh published theme colors and backgrounds together, including during navigation. Improve mobile user rows and prevent persistent mouse-focus outlines on page titles while retaining keyboard focus indicators.
- Fix Tdarr runtime resources, CSS paths, APIs and WebSockets through the protected proxy, with retry feedback for incomplete loading. An isolated native Tdarr 3.01.00 server was exercised through signup, dashboard and WebSocket traffic; deployment-specific compatibility still requires verification.

# 0.4.1 — 23 October 2026

- Remove nested scrolling from portal-builder side panels and size its preview to the full page content.
- Size access-guide previews to their full content, including phone preview widths, and use the builder page for scrolling.
- Flatten access-guide choice and step rows, group reorder arrows beside editing actions and give every breadcrumb the same height.
- Replace the account-menu language dropdown with direct flag/name buttons and a visible active-language check.
- Add a complete access-guide breadcrumb through the final device, clickable parent menus and an explicit device-picker return; fix the preview back link and save pending drafts before leaving.
- Keep the global header stationary between portal and wide admin pages and preserve the capsule slide during dynamic navigation.
- Implement the approved structured user profile, full-width user/group permission accordions and automatic account-menu language selection.
- Add the approved fixed administration sidebar and unify local navigation as sliding capsules with service logos and dynamic loading.
- Align user-list controls and add proportional logo resizing with an interactive crop/zoom tool in identity and setup.
- Improve text, links, capsules, account badges, focus indicators and bundled wordmarks across all six theme variants, especially Electric Lime light.
- Add dynamic user search/pagination, compact group settings, full-width password settings and consistent image upload controls.
- Test entered integration settings before saving; improve URL Base, authentication and network diagnostics.
- Proxy the Tdarr WebUI through authenticated Gatearr routes, including assets, native cookies and WebSockets.
- Limit customizable labels to public user journeys, show the edit language and retain native admin translations.
- Offer active email languages only and improve the factory invitation while preserving custom templates.
- Preserve existing grants while disabling new grants to unconfigured tools.
- Center CAPTCHA forms, remove the Member caption, fix quota spacing and make assistance language changes session-local.
- Keep default media/request widgets aligned with their apps and Tracearr on its own row.


# 0.4.0 — 23 October 2026

## New features

- Installer: five-stage multilingual installation with dynamic navigation, logo upload and initial preset selection; native PNG application logos and separate server/API tests.
- Conditional fresh-install portal defaults, editable afterward without replacing saved layouts; rename the blue preset to Blue Boréal.
- Capsule top navigation, native Emby/Jellyfin user photos, consolidated email-only preferences and guarded group rename/deletion.

- Three editable theme presets: Blue Boréal, Electric Lime and Neon Rose, each with light/dark variants and an animated personal appearance capsule.
- Tracearr personal statistics, explicit server/account matching, native interface access, and admin-only Tdarr interface access.
- Independent compact media, Seerr, Tracearr and Library updates blocks with optional app logos and audience priorities.
- Personal request availability and new-season announcements, optional Tracearr-dependent season email template and notification preferences.
- Locally bundled Cap protection for sign-in and password recovery, with per-form controls and aggregate statistics in Security → Captcha.

## Interface adjustments

- Keep all five setup steps aligned on small screens and show group permission differences as readable stacked comparisons on phones.
- Preserve the Jellyfin address placeholder and selected preset logo when switching installation languages.

- Review current native media-server and Seerr rights before adding group members; show only differences with a paginated, per-user confirmation and reject stale reviews.
- Apply the approved compact language panel with flags and inline settings; remove the assistance explanatory sentence from user account settings.

- Align email-template actions in a responsive grid and compact the appearance-policy controls.
- Use application logos for widget palette entries and disable them until their services are connected, including Jellyfin equivalents.

- Color presets preview immediately without changing navigation geometry; improve theme and translation spacing.
- Save themes, connections, emails, translations, security and notification preferences without reloading the page; the appearance capsule also switches in place.

- Media widgets automatically count the current user’s authorized content, without an administrator library selector or sums of overlapping views.
- Unified Applications & API overview, expandable service settings and read-only diagnostics, separate from saving.
- Existing compact controls and red/green status indicators are retained across light and dark themes.

## Security hardening

- Update the vulnerable Certifi trust store to 2026.10.19.
- Revalidate native account status for administrator requests and native-tool proxies; block privileged actions if verification fails.
- Refuse blank/passwordless native authentication, keep native administrator tokens out of automatic-login URLs, reject encoded proxy traversal, and suppress recovery-token referrers.
- Document public deployment requirements and the privileged native-service trust boundary.

## Bug fixes

- Align nested widget columns with application cards at every breakpoint, and keep metrics inside narrow blocks.
- Restore the Tracearr-dependent new-season template link in the main email menu.
- Keep captcha-required alerts on the current form and show a visible local checkmark after completion.

## Improvements

- Allow PNG/SVG uploads up to 5 MiB, remove remote image URLs across editors, and enforce the rule on legacy writes and public pages.
- Enforce Tracearr dependencies across mail editing and translation routes.

- User-scoped data, server-bound Tracearr identities, incremental library baselines and send-time notification authorization checks.
- Cap Core and solver assets run locally inside the Gatearr container, without a dashboard, Redis or cloud CAPTCHA account.

# Gatearr 0.3.4

## Bug fixes

- Recompute update availability against the installed version, including cached results; identical versions no longer trigger an update badge.
- Image widths set in the email builder are respected in editing, preview and saved messages.

## Interface adjustments

- Permission selections expand with the page, without nested scroll regions; library controls use the available width.
- Email template and language selectors, subject, save status and editing actions use an aligned responsive header.
- Email block deletion uses the same red danger button as the portal builder.
- Updates and feedback share the left overview column; customization reset is on the right.
- Release history shows each version once, expands only the installed version and marks it with a green current-version indicator.

## Improvements

- Reviewed interface terminology across all 21 bundled languages, with natural app wording for navigation, accounts, permissions, guides, email editing and updates; administrator overrides are preserved.

# Gatearr 0.3.3

## Bug fixes

- Public Emby/Jellyfin browser links and Emby automatic login share the application URL; legacy branding addresses migrate without replacing an existing application address.

- Group editors now share typed media-server controls with user editors, including schedules, devices, ratings and folders; unavailable settings are preserved.
- Uploaded identity logos are accepted and reused on the portal and sign-in page.

- Existing guide steps can be selected and edited, including older guides without step identifiers.
- Email account forms submit to the correct endpoint; changing the administrator email returns to sign-in.
- Unauthorized applications no longer reserve empty grid columns.
- Device icons are consistent in the guide editor, live preview and published pages.
- Responsive builder palettes, form controls and application selectors no longer overflow narrow screens.

## Interface adjustments

- Group editing separates members, media-server permissions, Seerr permissions and admin tools into tabs, preserving unsaved changes between tabs. Group headers and user/group admin tools share compact, consistent spacing.

- The full-width Logged as banner remains visible while scrolling. Account safety panels, clone forms and integration sections use consistent spacing.
- Email editing uses the portal builder layout: draggable block palette, central message canvas and property inspector, with undo/redo and desktop/phone previews.

- Compact user account cards, categorized native permission controls and named selections replace long permission tables and JSON fields.

- Transparent footer, clearer titles and consistent red/green library-access indicators. Shared 40 px form controls, compact utilities and understated horizontal navigation tabs.
- Invitation column shows confirmed emails and retains pending addresses for resending.
- Security settings are grouped under Users.
- Personalized portal-view action beside the user name and a full-width red Logged as banner.
- More natural navigation labels across supported languages, including Appearance instead of a literal branding translation in French.
- Collapsible application settings show one application at a time, with full-width fields, ordering controls and compact inactive entries.
- Guide step editing separates optional buttons, image uploads and duplicate/delete actions, with clear destination guidance and responsive spacing.

## Improvements

- Branding supports PNG/SVG logo uploads, logo/name display modes and a customizable browser-tab title.

- Read-only media-server and Seerr permission snapshots refresh every five minutes; stale forms are rejected without overwriting newer remote changes.
- Emby and Jellyfin policy editors use native device, folder and rating metadata, preserve unrelated settings and verify writes by reading them back.

- Block-based email editing with text, headings, images, dividers, buttons and live preview.
- Editable and translatable application subtitles.
- Release notes organized by category.
- Connection tests show resolved IP, reachability, response time and API status; SMTP connection testing verifies saved settings without sending an email.

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
