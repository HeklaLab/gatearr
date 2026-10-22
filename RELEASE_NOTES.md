# Gatearr 0.3.3 — public beta

This public beta refines the existing portal, account management, permissions and editors. Please [report bugs](https://github.com/HeklaLab/gatearr/issues/new?template=bug_report.yml) and [request features](https://github.com/HeklaLab/gatearr/issues/new?template=feature_request.yml) on GitHub.


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


## Upgrade

Back up `/data` and retain its encryption key. Pull `ghcr.io/heklalab/gatearr:0.3.3` (also `latest`), then run `docker compose up -d --wait`. Images support AMD64 and ARM64.

Migration 0019 centralizes the public Emby/Jellyfin browser URL in Applications & API, preserving an existing application address or carrying over the former Branding value. Other connections, accounts, permissions and published content are retained. See [UPGRADING.md](https://github.com/HeklaLab/gatearr/blob/main/UPGRADING.md).

## Validation

Automated tests and local HTTP/SMTP smoke use simulated servers; production Emby/Jellyfin/Seerr testing is not claimed. GitHub Actions additionally gates publication on Docker Compose smoke tests and multiarchitecture image publication.
