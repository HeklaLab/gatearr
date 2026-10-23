# Gatearr 0.4.1 — public beta

Gatearr 0.4.1 focuses on clearer administration, more consistent controls and fixes to builders, themes, translations and application connections.

## Administration and everyday use

- Fixed sidebar and shared sliding capsule tabs, with dynamic page loading and a stable header between Home and Administration.
- Structured user profiles and full-width permission sections for users and groups.
- User search as you type, with pagination of 10, 20, 50, 100 or all users.
- Guided dropdowns, consistent uploads and a logo preparation tool with automatic resizing, crop, fit and zoom.
- Compact language choices with flags and a visible active language; switching applies immediately.
- Better readability across Blue Boréal, Electric Lime and Neon Rose in light and dark appearances. Custom uploaded logos retain priority.

## Builders and personalization

- Complete device breadcrumbs through Windows, Mac, Linux, iPhone and Android, with clickable parent menus and a clear device-picker return.
- Compact guide rows with grouped up/down arrows and aligned editing actions.
- Portal and access-guide previews fit their content and responsive width; page scrolling replaces nested preview/panel scrollbars.
- Public-facing interface labels remain editable; administration uses bundled translations. The translation editor identifies its target language and groups repeated application subtitles.
- Email editors offer enabled languages only. Default invitations introduce one access portal, shared media credentials, self-service password recovery and device guides. Existing custom templates are preserved.

## Connections and fixes

- Test entered service URLs and API keys before saving, with separate reachability and authentication results.
- Clearer native URL Base, allowed-host and network diagnostics, plus Tracearr API token and media-server ID guidance.
- Protected Tdarr WebUI proxy with isolated native cookies, assets and WebSocket routing. Native authentication remains active; this provides interface access, not a Tdarr task-management API.
- Disable new tool grants for unconfigured services while preserving stored grants and enforcing access checks.
- Keep default media/request widgets below their matching applications, with Tracearr on a separate row. Existing customized portals are retained.
- Center both CAPTCHAs, correct quota and appearance-control spacing, remove the Member caption and keep assistance-language changes session-local.

## Upgrade and validation

Back up `/data`, including its encryption key, before updating. There are no additional database migrations from 0.4.0. Existing accounts, integration settings, uploaded logos, custom layouts and email templates remain in place. See [UPGRADING.md](https://github.com/HeklaLab/gatearr/blob/main/UPGRADING.md).

Automated tests use simulated native services. Browser checks cover the functional demo, desktop/mobile builders, device navigation, language switching and theme readability. The release workflow additionally gates publication on the complete test suite, Docker startup and the HTTP/SMTP smoke, then publishes AMD64 and ARM64 images. Compatibility with the user's actual Tdarr instance still needs deployment-specific verification.

Existing 0.4.0 screenshots are retained in the README; no screenshots were replaced for this release.
