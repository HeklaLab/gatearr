# Gatearr 0.4.0 — public beta

## New features

- Three editable theme presets: Blue Boréal, Electric Lime and Neon Rose, each with light and dark palettes. Administrators can enforce a variant or enable the animated, icon-only dark/light/automatic selector.
- Four independent, compact portal widgets: media library counts, Seerr requests/quotas, Tracearr viewing statistics and personal library updates. Logos, metrics and audience rules are configured by administrators. A visitor sees at most one widget of each type.
- Tracearr public v2 integration matches accounts by native user and server IDs. Personal statistics include viewing time, sessions, most-watched series, daily activity, comparison and explicitly estimated traffic.
- Personal library updates announce available Seerr requests and new seasons of watched series. Tracearr is required for watched-state expiry and new-season notifications. A localized, customizable email template and account preferences are available only when Tracearr is configured.
- Embedded Cap protects sign-in and password recovery, with independent switches, aggregate statistics and retention settings under Security → Captcha. Its worker, widget and WebAssembly files run locally in the same container; no cloud account, separate dashboard or Redis service is needed.
- Tracearr and Tdarr interfaces can be opened by explicitly authorized administrators. Tdarr provides interface access only.

## Interface adjustments

- Widgets align with corresponding application columns and adapt to narrow screens.
- Presets preview immediately; all presets share the same layout. Theme and translation spacing is refined.
- Supported settings, email and translation saves update in place; missing captcha shows an inline alert and preserves form input.

- Applications & API uses a common connection overview, expandable service panels, separate save/test controls and consistent technical diagnostics. Emby/Jellyfin and Seerr appear first.
- Widgets use flat, palette-aware layouts. Media counts automatically follow the current user’s native library/content permissions; no library selector is required. Seerr counters move out of application cards into widgets.
- Responsive layouts preserve shared compact buttons and red/green status indicators.

## Improvements

- PNG/SVG uploads allow up to 5 MiB. All image editors use uploads; remote image URLs are no longer accepted or loaded. Previously remote images need to be replaced through upload.
- Widget palette entries use native logos and stay disabled until their integration is connected. Theme policy controls are compact and email-template buttons align in a responsive grid.

- Widget access checks use current native permissions before cached aggregates are read. Request counts and announcements remain scoped to the current account.
- Background library monitoring establishes a silent first baseline, deduplicates announcements and rechecks consent, access and integration availability before sending queued email.
- Core new labels and the new-season email are localized across the bundled catalogs; administrator translations remain authoritative.

## Upgrade and validation

Back up the complete `/data` volume, including its encryption key, before upgrading. Migrations 0020 and 0021 retain existing accounts and configuration and move legacy Seerr application counters into widget blocks. To roll back to 0.3.4, restore the pre-upgrade backup. See UPGRADING.md for dependencies and native-interface requirements.

Local validation: **380 automated tests passed**, plus a full isolated HTTP/SMTP installation/account/group/editor smoke and 51 responsive page-width checks at 1280, 768, 390 and 320 px. Runtime Python and bundled CAPTCHA dependency audits found no known vulnerabilities at the review time. Native services were simulated. Docker build/startup and multiarchitecture images are gated by GitHub Actions; production native services and public TLS were not tested locally.

See [validation details](https://github.com/HeklaLab/gatearr/blob/main/VALIDATION.md) and [security boundaries](https://github.com/HeklaLab/gatearr/blob/main/SECURITY_REVIEW.md). Back up `/data`, retain its encryption key, and complete first setup privately before public exposure.

## Installation, accounts and administration

- Five dynamic installation stages, all 21 bundled languages, logo upload, initial preset selection and separate server/API connection tests.
- Capsule navigation with a sliding active item, account dropdown and native profile pictures synchronized with Emby/Jellyfin.
- Contextual email-only account preferences; separate email-template and SMTP tabs.
- Conditional starter portal, compact admin mosaic, theme-aware default logos and refreshed language rows with flags.
- Group renaming and guarded deletion, plus current native permission/library comparisons before adding users. Bulk additions use a paginated per-user review; stale confirmations are refused.

## Interface preview

Fictional demo accounts and local simulated services; these screenshots show the implemented application.

![Gatearr 0.4.0 portal](https://raw.githubusercontent.com/HeklaLab/gatearr/v0.4.0/screenshots/gatearr-home-v040.png)

![Gatearr 0.4.0 themes](https://raw.githubusercontent.com/HeklaLab/gatearr/v0.4.0/screenshots/gatearr-themes-v040.png)

![Gatearr 0.4.0 application connections](https://raw.githubusercontent.com/HeklaLab/gatearr/v0.4.0/screenshots/gatearr-integrations-v040.png)
