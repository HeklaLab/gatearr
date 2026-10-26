# Gatearr — Emby & Jellyfin account portal

**Your media server. One front door.**

A free, open-source, self-hosted account portal for **Emby and Jellyfin**. Give your users one place to access their media services, manage their accounts, reset forgotten passwords and follow device connection guides. Manage user groups, library permissions and optional Seerr requests from an interface you can make your own.

**0.4.3 public beta** improves application cards, image editing, guide navigation and integration reliability. Gatearr entered public beta with v0.3.2. Free and open source (MIT), with Docker images for AMD64 and ARM64. Real-world feedback will help shape the next releases.

[Download the beta](https://github.com/HeklaLab/gatearr/releases/tag/v0.4.3) · [Report a bug](https://github.com/HeklaLab/gatearr/issues/new?template=bug_report.yml) · [Request a feature](https://github.com/HeklaLab/gatearr/issues/new?template=feature_request.yml) · [Roadmap](ROADMAP.md)

If something is broken, confusing or missing, please open an issue. Include versions, deployment details and reproduction steps; remove secrets and personal information from logs/screenshots. This is an early beta: back up persistent data and test permission changes with a limited account before applying them broadly.

## Quick start

**Requires an existing Emby/Jellyfin server and Docker Compose v2.** Seerr, Tracearr and the administration tools are optional. SMTP enables invitations and self-service password recovery.

1. Download [gatearr-docker.zip for v0.4.3](https://github.com/HeklaLab/gatearr/releases/download/v0.4.3/gatearr-docker.zip) and extract it.
2. Review the [installation prerequisites](#installation-prerequisites), then run from the extracted folder:

   ```sh
   docker compose config --quiet
   docker compose pull
   docker compose run --rm --no-deps gatearr python -m app.bootstrap --check
   docker compose up -d --wait
   ```

3. Open [http://localhost:8000/setup](http://localhost:8000/setup) on the Docker host and complete the wizard with your media-server API address/key and an existing administrator account. Choose your portal name, language and theme; add optional services and email delivery when ready.

Complete setup privately. For access from other devices or the internet, configure `PUBLIC_URL`, your existing HTTPS reverse proxy and the [documented security boundaries](SECURITY_REVIEW.md). Keep the persistent `/data` volume, including `bootstrap.json`.

**Docker:** `ghcr.io/heklalab/gatearr:0.4.3` · **Architectures:** AMD64 / ARM64 · **License:** MIT

[Windows instructions](#windows--docker-desktop) · [Full Docker instructions](#start-with-docker) · [Upgrade an existing installation](UPGRADING.md) · [Community on Reddit](https://www.reddit.com/r/gatearr/)

## Interface preview — previous release (0.4.1)

Real screenshots of Gatearr 0.4.3 running locally with the **Blue Boréal** theme and the original Gatearr logo. The reset demo uses fictional people, sample libraries and simulated integrations; no production accounts or credentials appear below.

### Your portal

The standard member portal shows media counts and request quotas inside their application cards, with viewing activity on its own row.

![Gatearr 0.4.3 default Blue Boréal portal](screenshots/gatearr-home-v043.jpg)

### Administration and people

A fixed sidebar and shared capsule tabs lead to live user search, structured profiles and group permissions.

![Gatearr 0.4.3 administration](screenshots/gatearr-admin-v043.jpg)

![Gatearr 0.4.3 users with fictional accounts](screenshots/gatearr-users-v043.jpg)

![Gatearr 0.4.3 structured user profile](screenshots/gatearr-user-profile-v043.jpg)

### Visual portal builder

Build responsive pages with application rows, independent widgets, columns, text and images. The preview follows its content without nested scrolling.

![Gatearr 0.4.3 portal builder](screenshots/gatearr-builder-v043.jpg)

### Applications and appearance

Service status and connection settings share one overview. Blue Boréal is shown here; Electric Lime and Neon Rose remain available as alternate presets.

![Gatearr 0.4.3 application connection overview](screenshots/gatearr-integrations-v043.jpg)

![Gatearr 0.4.3 appearance settings with Blue Boréal selected](screenshots/gatearr-themes-v043.jpg)

### Groups and translations

Manage members, native permissions and library access through shared groups. Enabled languages are displayed with flags and a clear editing language.

![Gatearr 0.4.3 group permissions](screenshots/gatearr-group-review-v043.jpg)

![Gatearr 0.4.3 translation center](screenshots/gatearr-languages-v043.jpg)

### Updates

![Gatearr 0.4.3 release history grouped by series](screenshots/gatearr-updates-v043.jpg)

### First installation

The setup assistant configures portal identity, language, initial theme and media-server access.

![Gatearr 0.4.3 first installation](screenshots/gatearr-setup-v043.jpg)

<details>
<summary>More screenshots: mobile portal, account, guides, emails and sign-in</summary>

### Mobile portal

![Gatearr 0.4.3 mobile Blue Boréal portal](screenshots/gatearr-home-mobile-v043.jpg)

### Account and user groups

![Gatearr 0.4.3 account settings](screenshots/gatearr-account-v043.jpg)

![Gatearr 0.4.3 user groups](screenshots/gatearr-groups-v043.jpg)

### Device guides and their editor

![Gatearr 0.4.3 device picker](screenshots/gatearr-devices-v043.jpg)

![Gatearr 0.4.3 Smart TV connection guide](screenshots/gatearr-guide-v043.jpg)

![Gatearr 0.4.3 guide builder with complete device breadcrumbs](screenshots/gatearr-guide-editor-v043.jpg)

### Invitation template

![Gatearr 0.4.3 invitation email editor](screenshots/gatearr-emails-v043.jpg)

### Sign-in and account recovery

![Gatearr 0.4.3 sign-in page](screenshots/gatearr-login-v043.jpg)

![Gatearr 0.4.3 password recovery](screenshots/gatearr-password-reset-v043.jpg)

</details>

## What's new in 0.4.3

- Independent direct-link, embedded-tool and guide behavior for each application card; same-named custom apps remain editable.
- Image sizing in pixels/percent, corrected alignment, large-image resizing and saved-image previews.
- Consistent builder navigation, clearer clickable guide choices and diffuse device artwork.
- Theme/spacing fixes, improved Tdarr loading and safer Emby browser opening.
- Release history grouped by series and a roadmap shortcut.

See [release notes](RELEASE_NOTES.md), [upgrade instructions](UPGRADING.md) and the [roadmap](ROADMAP.md). The gallery above shows the current 0.4.3 interface.

## Features introduced in 0.4.0

- **First installation:** five dynamic stages, all 21 bundled interface languages, portal logo and initial preset, native account claim, optional applications with separate server/API tests, SMTP and final review.
- **Appearance:** three editable light/dark presets, matching default logos, an animated icon-only appearance capsule in the account menu, and immediate previews. Administrators can enforce dark/light or leave the choice to users.
- **Widgets:** native-library counts, Seerr requests/quotas, Tracearr activity and Library updates. Administrators control metrics, optional logos and audience; the personal update widget is independent of email subscriptions.
- **Notifications:** request availability and new-season announcements; optional season emails require Tracearr, SMTP, a verified address and user opt-in. Initial synchronization creates a silent baseline.
- **People:** native Emby/Jellyfin profile pictures synchronized in both directions, compact groups, rename/deletion safeguards, and reviewed native permissions before adding members.
- **Applications:** consistent connection diagnostics, Tracearr integration and admin-only Tdarr interface access. Tdarr does not manage jobs through Gatearr.
- **Captcha:** Cap is bundled inside the same container for sign-in/recovery, with per-form controls and aggregate statistics under Security → Captcha.
- **Editing:** upload-only PNG/SVG images up to 5 MiB, separate email templates/SMTP tabs, refreshed language management and dynamic saves on supported forms.

Read the [full changelog](CHANGELOG.md), [upgrade instructions](UPGRADING.md), [validation results](VALIDATION.md) and [security boundaries](SECURITY_REVIEW.md).

## 0.4.0 configuration

- **Appearance → Theme:** apply Blue Boréal, Electric Lime or Neon Rose; edit both light and dark palettes. Publishing a preset replaces colors, not layouts or content. An administrator can force a variant or allow the personal Dark/Light/Auto capsule.
- **Applications & API:** unified reachability/authentication diagnostics for Emby/Jellyfin, Seerr, Radarr, Sonarr, Bazarr, Tracearr and Tdarr. Saving and testing are separate actions. No private key is sent to a browser.
- **Portal builder:** add compact Media, Seerr, Tracearr and Library updates blocks. Logos are optional administrator settings. Media counts automatically use the current user’s native library/content permissions, without an administrator library selector. Distinct copies remain distinct if both are authorized; this is not title-based deduplication. Audiences can target roles or groups; group-specific blocks outrank roles, which outrank general blocks. Use distinct priorities for otherwise overlapping blocks.
- **Tracearr:** public API v2 with identity correlation is required. Select the corresponding Tracearr server ID when multiple Emby/Jellyfin servers are monitored. A username is never used to identify a person. A feature fails closed when the required API/identity is missing.
- **Library updates:** completed Seerr requests and new seasons of previously watched series. The first successful synchronization establishes a baseline and sends no historical notifications. Personal feeds check library access. New-season emails require Tracearr, SMTP, a verified address and the user's opt-in. Configure their template in the email builder while Tracearr is enabled.
- **Native interfaces:** Radarr/Sonarr/Bazarr retain the protected path proxy and required native URL Base. Tracearr and Tdarr use their configured browser-reachable public interface address; their own authentication and frame restrictions remain in force. Tdarr has no job-management integration and is restricted to explicitly authorized Gatearr administrators.
- **Security → Captcha:** Cap protects sign-in and recovery by default. All JavaScript/WASM assets are bundled. The container includes one lightweight local Node worker; no separate container, Redis or cloud key is needed. Token validation is server-side, session/form-bound and atomic single-use. Existing sign-in rate limits remain active.

Tracearr statistics are scoped to the selected server and use UTC calendar windows. Network traffic is an estimate from kbps × recorded duration, never a measured byte total. Unsupported metrics do not display invented values. Library refreshes are bounded, incremental background tasks; initial visibility and delivery follow successful synchronization.

## Why Gatearr?

Sharing a media server with family or friends can turn its owner into the help desk: reset another password, repeat permissions for several users, explain how to connect a TV and send the correct URL again. Gatearr was built to address these needs in one place.

| Need | What Gatearr provides |
| --- | --- |
| Forgotten passwords | Email-based self-service password recovery, verification and invitations for accounts on the connected media server. SMTP and an account email are required. |
| Repeated account configuration | User groups managing libraries, Emby permissions, Seerr permissions/quotas and Gatearr/admin-tool access. Each user belongs to at most one group. |
| Permission management | Edit supported media policy fields: streams, downloads, subtitles, remote access and more. Read-back indicators distinguish verified, pending, different and failed values. |
| Helping users connect | Visual **Access guides** with nested device choices, illustrated steps and store/download links. Starter Emby guides cover browser, Windows, Mac, Linux, Android, iPhone and Smart TV. |
| A portal that looks like your own | Drag-and-drop **Login screen**, **Portal** and **Footer** builders, live previews, application rows, rich text, uploaded logos/images, menus, colors, gradients, button/hover styles and editable light/dark presets. |
| Seerr integration | Optional request quotas per user/group, access and permissions, email/language/notification synchronization and independent request/quota widgets for administrators and members. |
| Native administration tools | Individually granted Radarr, Sonarr and Bazarr interfaces inside Gatearr at `/tools/...`, plus Tracearr and Tdarr interface access. Grants include their full native interface and administrative capabilities. |
| Account support | Username/email/password administration, account-change emails, audited assistance sessions and readable activity logs. |
| Localization | Default language chosen at setup, twenty additional pretranslated packs, and **Translations / Labels** for fixed interface text and custom content. |
| Easy deployment and updates | One application container, a persistent volume, an installation wizard, connection health checks, changelog and Docker pulls. |

Gatearr is a separate web application, not an official Emby/Jellyfin product or an Emby plugin. Groups live in Gatearr; supported settings are applied through connected applications’ APIs. It does not create native Emby groups.

## One address to give your users

Users start at Gatearr, sign in with their media username **or the email registered on their Gatearr account**, manage their account and open applications they are allowed to use. Passwords are checked against the connected media server.

A typical setup behind your existing HTTPS reverse proxy:

| Application | Example public address |
| --- | --- |
| Gatearr — the homepage you share | `https://example.com` |
| Emby or Jellyfin | `https://play.example.com` |
| Seerr — optional requests application | `https://request.example.com` |

These are reserved example domains. API addresses can remain private; browser/application URLs must be reachable by your users. No reverse proxy is bundled. Emby browser handoff and optional Seerr session handoff have specific prerequisites documented below; this is not universal SSO.

**Email recovery changes the password on the connected media server. It does not reset an Emby Connect/community account or recover a server that was never connected to Gatearr.**

## Portal builder and Access guides

Open **Administration → Appearance → Portal builder**, then choose **Login screen**, **Portal**, **Access guide** or **Footer**. Drag blocks into the live preview and click to edit. Preview desktop, tablet or phone layouts. Configure login-form placement, menus, rich text, links, images, footer columns and colors. Drafts autosave; **Publish** makes them visible to users.

Each **Applications** block fills one row. Choose the **Number of applications** (up to six), select at most that many and drag them into order. Use one row for Emby/Seerr and another for Sonarr/Bazarr/**My account**, for example. Applications appear only to users who have access. Existing oversized grids are adapted into rows while retaining selection order.

An application can open a direct link or its **Access guide**. Guide choices can be nested and reordered; tutorials have rich steps, images and download links. Use `{server_url}`, `{server_host}`, `{server_port}` and `{username}` in instructions. Emby starts with guides; Seerr defaults to a direct link and can have custom guides. Radarr/Sonarr/Bazarr open their integrated interfaces and do not use guides.

Edit the light/dark palettes and gradients in **Appearance → Theme** with a live preview, or customize page/block colors in the builder. Official application PNG logos and the searchable Font Awesome Free collection are bundled. Validated PNG/SVG uploads persist in the database. Footer content supports columns, rich text, images and links.

**Updates → Reset customized content** restores starter pages, guides, labels, theme and application display while retaining API/SMTP connections, users, groups, permissions and active languages. Confirmation is required.

### Included languages

Twenty-one language catalogs are bundled. Only the setup language is enabled initially; English can be disabled when another language is active, and the last active language cannot be disabled. **Translations / Labels** separates fixed labels from custom content. One user language applies to the interface, emails and supported Seerr settings.

Packs were initially machine-translated with automated placeholder checks; comprehensive human review is not claimed. Corrections are welcome. Custom content needs its own translations. Arabic/Hebrew support right-to-left layout. No translation service is contacted at runtime.

## Public exposure and security

Gatearr holds privileged native-service credentials. Read the [security review and required deployment boundaries](SECURITY_REVIEW.md) before internet exposure. Complete setup privately, use HTTPS, keep backend ports private, and restrict native-tool access to trusted operators. A compromised Gatearr process or administrator can compromise the connected media server.

## Installation prerequisites

Before starting Gatearr, check:

1. **Docker Engine/Desktop and Compose v2** are installed and running: `docker version` and `docker compose version`. On Windows, select Linux containers. On Linux follow the [official Docker installation instructions](https://docs.docker.com/engine/install/), including permission to use the Docker daemon. Package-manager commands require administrator privileges; upgrading/rebooting the operating system is separate from installing Gatearr.
2. **Persistent writable storage** is available on a local disk. Keep `/data`, including `bootstrap.json`, for the lifetime of the installation. SQLite uses WAL and requires directory access for the database, WAL and shared-memory files; network filesystems are not supported.
3. **Emby/Jellyfin** is reachable from inside Docker and an administrator API key is available. `localhost` inside the container refers to that container. Use a shared Docker service name, the server's LAN address, or `host.docker.internal` for a server on Windows/Mac Docker Desktop. Linux host access needs a LAN address or an explicit host-gateway mapping. Check the server firewall.
4. **Public HTTPS** is provided by your existing reverse proxy. Point both A and any AAAA DNS records at the proxy's actual public endpoint; forward the required ports to that proxy. ACME certificate validation must reach it on port 80 and/or 443, depending on the challenge. A stale AAAA record or a record pointing at another web host can fail certificate issuance even if local access works. Keep the initial setup private until completed.
5. **SMTP** is needed for invitations, recovery and account-change notifications. It can be skipped during setup, but direct admin email/password changes require SMTP and a recipient address. Confirm host, port, TLS mode, sender and credentials.

### Linux bind-mounted data: prepare ownership first

The image runs as UID **10001**, GID **10001**, without root privileges. If you mount a host directory, prepare that specific directory before starting:

```sh
sudo install -d -m 0750 -o 10001 -g 10001 /opt/emby/gatearr
```

Example service volume:

```yaml
volumes:
  - /opt/emby/gatearr:/data
```

For an existing directory, stop Gatearr and back it up before correcting ownership of its files. Do not change permissions on the entire media-server directory, do not delete `bootstrap.json`, and do not use `chmod 777`. A Docker named volume is used by the supplied Compose and avoids manual host-directory preparation on a fresh installation.

Check access **before** starting the application:

```sh
docker compose run --rm --no-deps gatearr python -m app.bootstrap --check
```

This checks the running UID/GID's access without replacing secrets or modifying the database. Startup also checks access and prints a concise diagnostic if it cannot write to storage. Existing older error lines can remain in Docker logs after a successful restart; use `docker compose logs --since=2m gatearr` and check health/current state.

## Start with Docker

Download the release's `gatearr-docker.zip`, extract it and run these commands from the extracted folder. The default configuration is ready to start; complete your installation in the web wizard:

```sh
docker compose config --quiet
docker compose pull
docker compose run --rm --no-deps gatearr python -m app.bootstrap --check
docker compose up -d --wait
```

Default image: `ghcr.io/heklalab/gatearr:latest`. Pin `:0.4.3` for a controlled version. Public container pulls require no GitHub credentials. The source repository and release downloads are public; opening a GitHub issue requires a GitHub account.

Open `http://localhost:8000/setup`. Edit `PORT`, `BIND_ADDRESS` and `PUBLIC_URL` for your deployment. For LAN testing set `BIND_ADDRESS=0.0.0.0` and `PUBLIC_URL=http://YOUR_SERVER_IP:8000`. Ports 80/443 normally belong to your existing HTTPS proxy; Gatearr serves HTTP internally on 8000. There is no bundled Caddy or second TLS listener.

The session/encryption secret is generated once in `/data/bootstrap.json` when `SECRET_KEY` is empty. Retain it. API keys are entered in the wizard/API connections and stored encrypted. No installation token is required.

### Windows / Docker Desktop

```powershell
cd C:\docker-test\gatearr
docker compose pull
docker compose up -d --wait
```

Open `http://localhost:8000/setup` and complete the web wizard. For Emby on the same PC use `http://host.docker.internal:8096/emby` as the API URL. Browser/app URLs must be reachable by the actual users; another device cannot use your PC's `localhost`.

### First-run wizard

Five steps: portal identity/media server → existing media administrator selection → optional applications on one screen → optional email → finish. All 21 bundled interface languages, a logo upload and an initial theme preset are available from the first step.

The first Gatearr administrator is an existing active media account whose password is verified. Other imported accounts can later receive the Gatearr admin role. Media administrator status does not automatically grant Gatearr administration. The first-admin selection is browser-bound, expires after 30 minutes and cannot be claimed twice.

When a connection check fails, non-secret fields remain filled in, with an error on the same page. Passwords/API keys are not echoed into the response. After setup, connection settings remain in API connections and the wizard is hidden.

## Existing reverse proxy

Connect Gatearr to the same Docker network as your existing proxy, or use an external shared network in a Compose override:

```yaml
services:
  gatearr:
    networks:
      default: {}
      proxy: {}
networks:
  proxy:
    external: true
    name: YOUR_EXISTING_PROXY_NETWORK
```

Example existing Caddy site:

```caddyfile
accounts.example.com {
    reverse_proxy gatearr:8000
}
```

Set `PUBLIC_URL=https://accounts.example.com`, `COOKIE_SECURE=true`, and `TRUSTED_PROXY_IPS` to the proxy's exact address/CIDR as seen by Gatearr. If already installed, update the stored public URL in Appearance too. Validate the Caddy configuration before reloading it. A formatting warning is different from a failed certificate challenge; use the actual error/status to diagnose it. `GET /healthz` and `HEAD /healthz` check application/database readiness.

## Administration

- **Appearance**: configurable name, uploaded logo and browser-tab title, Portal builder (including Access guides and Footer), and Theme with live preview.
- **Users**: accounts, group membership, libraries/media policies, Seerr permissions/quotas, admin-tool access and assistance.
- **Applications & API**: application links, private/public addresses, connections and health checks in one place.
- **Emails**: separate template and SMTP tabs; localized invitation/recovery/verification/account-change templates and a Tracearr-dependent new-season template.
- **Security**: password complexity and local Captcha protection for sign-in/recovery, with per-form controls and aggregate statistics. Native password rules also apply.
- **Translations / Labels**: active languages, fixed labels and custom content translations.
- **Activity log**: readable changes with actor, affected user, result and selected before/after values, plus administrator-only SMTP history for new email attempts. Secrets and message bodies are excluded; SMTP acceptance does not prove inbox delivery.
- **Updates and changelog**: release checks, installed version, changelog, feedback links and customization reset.

### Account management and assistance

Administrators can send verification/reset links, edit usernames or directly change an email/password. Renaming updates the native media login and the matched Seerr display name; failed Seerr updates are shown and retried. Users sign in again after a rename. Direct changes queue a localized notification; email changes notify the old and new addresses. Passwords are never emailed. Existing Gatearr sessions and recovery tokens are invalidated after direct credential changes. SMTP failures are retried by the encrypted mail outbox and recorded in container logs.

**View portal as [user name]** starts an audited, 30-minute assistance session with a sticky, full-width red **Logged as** banner and return button. Gatearr account/settings writes are blocked during assistance. The user's own tools/permissions control what is displayed. Automatic Emby/Seerr links need a still-valid session created when that member previously signed in to Gatearr. If unavailable, the interface asks the member to sign in again. No user password is retained. Service links open genuine remote user sessions: actions performed there have that user's normal effects. Returning to the administrator's portal does not close already-open external browser tabs.

Emby browser login verifies the captured user token before handoff. Jellyfin web clients do not universally support this URI login scheme, so Gatearr reports the limitation instead of substituting an administrator API key.

### Media permissions and groups

User and group editors separate media-server permissions, Seerr permissions and admin tools into tabs. Native controls replace JSON fields for supported schedules, devices, folders, ratings and tags. Gatearr refreshes observed media-server and Seerr permissions every five minutes and rejects stale saves. Public media browser addresses are configured only in **Applications & API**.

Review/edit the fields actually returned by the media server: streams, downloads, subtitles, remote access and other policy settings. Authentication providers and server-maintained counters remain read-only. Sensitive administrator/disabled changes require explicit confirmation; the last active Gatearr admin is protected.

Before adding users, Gatearr compares their current native permissions, libraries and application access with the group. Only differences are displayed, one user at a time for bulk additions. Confirmations expire and are rejected if the underlying rights or group change.

Each user belongs to at most one group. Group membership locks individual library, permission and application-access editing; edit the owning group instead. Removing membership restores captured original values for settings previously managed by the group. Existing multi-group configurations are migrated as described in [UPGRADING.md](UPGRADING.md).

Seerr permissions and movie/season quotas can be managed per user or group. Unrelated settings are preserved and writes are read back. Seerr’s native rules still apply: users with **Manage Users** are exempt from request quotas, and protected owner/admin settings cannot always be changed through its API. Request and quota counters use independent portal widgets, with administrator-selected metrics, optional logos and role/group audiences.

Indicators distinguish verified values, pending/drift and failures. Observing remote changes does not silently overwrite them. Deactivation blocks Gatearr, rotates configured remote passwords and blocks Gatearr recovery; reactivation permits a new reset. Native sessions and recovery paths remain governed by their applications; see the upgrade notes.

Emby libraries use virtual-folder GUIDs, not numeric navigation IDs. Jellyfin uses its own adapter. Cloning copies the selected policy/configuration/home preferences through native media APIs; validate a restricted account on your actual server before granting access broadly.

### Themes, footer and icons

Blue Boréal, Electric Lime and Neon Rose each provide editable light/dark palettes. Apply a preset in Appearance → Theme to preview its colors and matching default logo, customize either palette if needed, then publish. Presets replace colors without changing layout. Administrators can enforce dark/light or allow the personal appearance capsule in the account menu. Custom uploaded logos take priority, and upgrades retain existing custom colors.

The footer is centered and supports one, two or three rich-text columns, links and uploaded images. Save a draft, preview it, then publish. Only the selected number of column editors is shown. Each has rich text and direct PNG/SVG image upload. Legacy content is prefilled into one editable column. Hidden columns are kept in the draft and restored when you increase the count.

Icons accept validated PNG/SVG uploads or the complete bundled Font Awesome Free 6.7.2 collection (2,060 icons across Solid, Regular and Brands) through a searchable visual picker. PNG limit: 5 MB and 1024×1024; SVG limit: 5 MB with a strict element/attribute allowlist. Scripts, embedded documents and external references are refused. Assets persist in SQLite and are served as inert images. Images throughout the portal, guides, footer and emails accept uploads only (plus bundled application/brand assets); remote image URLs are not accepted or loaded. Application and destination links remain available. Service icons also support Font Awesome. Font Awesome is bundled locally under its included license; no external font service is required.

## Automatic Seerr login

Configure Seerr's API and public HTTPS URL, then enable automatic login in API connections. Seerr must already contain the same media account, matched by immutable media ID. Users sign back in to Gatearr after activation.

On the **Seerr hostname**, add this route to your existing proxy, adapting upstreams to your Docker network:

```caddyfile
requests.example.com {
    handle /gatearr-login {
        reverse_proxy gatearr:8000
    }
    handle {
        reverse_proxy seerr:5055
    }
}
```

Preserve Host. The bridge uses a one-use 60-second POST ticket; no password/key is included in links. Sessions are encrypted and bound to live Gatearr sessions; assistance tickets are also bound to the issuing admin's active assistance session. Gatearr attempts remote logout for its captured session. Independently created service sessions follow their own expiration rules.

Seerr email/language/notification synchronization preserves unrelated settings. Notification policy may be unmanaged, user-selectable or forced. Email delivery must also be configured in Seerr.

## Radarr / Sonarr / Bazarr admin tools

Each tool has its own optional connection and its own user checkbox under **Admin tools**: **Admin Gatearr**, **Access Radarr**, **Access Sonarr**, **Access Bazarr**. Tool access does not require the Gatearr admin role. Access checkboxes can be set before connecting a tool; its interface remains unavailable until the connection is configured and enabled.

**These grants provide the complete native tool interface and its administrative actions.** They are not per-library or read-only native application roles. Gatearr checks the grant on every HTTP request and periodically during WebSocket connections; logout/revocation invalidates access.

For each tool:

1. In the native application's general settings, set **URL Base** to `/tools/radarr/app`, `/tools/sonarr/app` or `/tools/bazarr/app`, respectively. Restart the native app after changing it. Its private API and web UI will now use that prefix too.
2. In Gatearr, enter the private server root URL (for example `http://radarr:7878`) or the full prefixed private URL, plus the API key. Gatearr verifies the API under the required prefix. No public tool URL is requested.
3. Your existing main Gatearr proxy already handles the tools. No extra public hostname or Caddy site is needed. `/tools/radarr`, `/tools/sonarr` and `/tools/bazarr` show the native application inside the Gatearr interface.
4. For automatic UI login, use the native [Radarr/Sonarr external authentication setting](https://wiki.servarr.com/radarr/settings) and Bazarr proxy-only access. Keep native ports restricted to the private Docker/LAN network. Gatearr does not weaken or alter native authentication automatically. Forms authentication can otherwise show an additional login screen.
5. Grant each tool explicitly through the user’s **Groups and admin tools** tab or their owning group, including for Gatearr administrators. Select the tool in an Applications block to place it on the portal; visibility follows the grant and enabled connection. The wrapper and every proxied HTTP/WebSocket request check the live Gatearr session and grant. Revoking the grant or signing out removes access.

The iframe shares Gatearr's browser origin. Only connect trusted native applications: this path-based arrangement is not an origin-isolation boundary, and native scripts have the same origin as the portal. Grants provide the full native interface, including administrative capabilities and configuration normally visible there. Browser cookies/Authorization/API-key headers are stripped before upstream forwarding; configured API credentials are added server-side. Arbitrary targets and redirects outside the tool prefix are refused. HTTP bodies are capped at 32 MB, WebSocket messages at 4 MB.

## Updates, backup and recovery

Back up **all of `/data`**, including `bootstrap.json`, before updating. Keep the same named volume/bind mount and the exact existing `SECRET_KEY` if supplied explicitly. Never use `docker compose down -v` to update.

```sh
docker compose pull
docker compose up -d --wait
docker compose logs --since=2m gatearr
```

Startup runs migrations automatically. See [UPGRADING.md](UPGRADING.md) before upgrading from older packages. The historical v0.2.0 migration removed the former Tracearr connection secrets, queued jobs/checks and newsletter fields. Version 0.4.0 introduces a new Tracearr integration; configure its current API connection rather than restoring the retired credentials. Other accounts, mappings, roles, emails, Seerr/media connections and custom portal content remain.

Server-side role recovery uses an existing media account:

```sh
docker compose exec gatearr python -m app.admin_cli list-users
docker compose exec gatearr python -m app.admin_cli grant-admin MEDIA_USER_ID
```

## Development and validation

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
docker compose -f compose.demo.yaml up -d --build --wait
python scripts/smoke.py
```

The demo uses simulated media/Seerr services and Mailpit. At setup use `http://mock-emby:8096/emby`, key `demo-emby-key`, and first administrator `portal-admin` / `AdminPassword123!`. The ordinary account is `demo` / `DemoPassword123!`; the smoke test changes it to `ResetPassword123!`. These credentials are for the isolated demo only.

Build from source with `docker compose -f compose.yaml -f compose.build.yaml up -d --build --wait`. See [VALIDATION.md](VALIDATION.md), [CHANGELOG.md](CHANGELOG.md) and [PUBLISHING.md](PUBLISHING.md). Live Emby/Jellyfin/Seerr/tool versions and your actual proxy need validation in your environment; simulator tests do not establish compatibility with every native version.

## Contributing and feedback

Help improve this first public beta: [report bugs](https://github.com/HeklaLab/gatearr/issues/new?template=bug_report.yml), [request features](https://github.com/HeklaLab/gatearr/issues/new?template=feature_request.yml), or contribute documentation, translations and pull requests. See [CONTRIBUTING.md](CONTRIBUTING.md).

Gatearr is independently developed and is not affiliated with or endorsed by Emby, Jellyfin, Seerr or the other integrated applications. Their names/logos belong to their respective owners.


### Portal defaults and native profile pictures

The five-step installer configures portal identity/media server, the first administrator, optional applications, outgoing email and a final summary. All 21 bundled interface languages are available during setup. Changing language translates the current screen without discarding entered fields. PNG/SVG logo uploads are limited to 5 MiB; the supplied Gatearr logo is shown initially. Choose Blue Boréal, Electric Lime or Neon Rose before continuing. Application tests distinguish unauthenticated HTTP reachability from authenticated API validation; Tdarr has an interface check only.

Finishing a fresh installation creates Welcome, media/Seerr application cards, one to three corresponding statistics widgets, an administrator-only row of configured admin tools and a full-width My account card. Existing saved portal designs are preserved. The portal builder can change every default afterward. Application logos are bundled PNG files; Jellyfin uses its own logo and native identity.

The top navigation uses one capsule beside the account menu. Appearance controls live inside that menu. Native profile photos appear in navigation, the user list and account pages. PNG/JPEG uploads (up to 5 MiB) update the corresponding Emby/Jellyfin profile. Native image tags invalidate Gatearr's private bounded cache during user synchronization or profile refresh. A missing or inaccessible image falls back to the user's initial. Native credentials never appear in photo URLs.

Account notification preferences control email subscriptions only. They are hidden when outgoing email or the relevant integration is unavailable; portal widgets remain administrator-controlled. Group settings support renaming and deletion. Keeping users restores the permissions managed by the removed group. Deleting members also deletes their native media and linked Seerr accounts, including Seerr requests; this requires a checkbox and typing DELETE. Own accounts and administrators are protected. Remote deletions cannot form a single transaction: failures stop the operation and retain remaining members for review and retry.
