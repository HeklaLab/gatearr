# Gatearr

A customizable, self-hosted account portal for Emby and Jellyfin. Sign in with your media account, manage your account and open the services published by your administrator.

Python 3.12, FastAPI, SQLAlchemy/Alembic and SQLite/WAL. One application container and one persistent data volume. English is the source language. Twenty additional pretranslated language packs are bundled but disabled by default; activate them and edit interface, content and email text in Translations. No reverse proxy is bundled.

## Visual studio (0.3.0)

Open **Administration → Branding → Visual studio** and choose **Before sign-in**, **After sign-in** or **Footer**. Drag a block from the palette into the real page preview, or click to add it. Click a block to edit its text, width, alignment, visibility, image and colors. Columns accept nested blocks; choose one, two or three columns without entering layout numbers. The sign-in form can be moved and aligned left, center or right, but a sign-in page must retain exactly one visible form.

Page colors and individual block colors include backgrounds, gradients, text, buttons and hover states. Desktop, tablet and phone previews share the same renderer as the published pages. Undo/redo covers this editing session; draft changes autosave. **Publish** makes them visible to users. Conflicting administrator edits stop with a reload message instead of silently overwriting another draft. Existing English content is edited once; its translations live in Translations. Uploaded images are bounded and sanitized PNG/SVG assets stored in the persistent database.

Open **Services → Edit choices and guides** to set an application's behavior: open a link, present choices, or show a guide. Choice cards can be moved, reordered and nested via breadcrumbs. Each guide has a visual step list, rich instructions, image uploads and optional download buttons. Insert `{server_url}`, `{server_host}`, `{server_port}` or `{username}` to reuse the configured public connection details. Publish guides before publishing choices that refer to them. Previous guide links and published snapshots are retained.

The bundled default logos are served locally. Custom uploads and explicitly chosen Font Awesome icons remain in use. My account follows the applications rather than appearing before newly enabled tools. API connections has a service-status overview and separate, equal-width media/Seerr forms; it contains no translation controls.

### Included languages

The English source plus twenty language packs are included. Only English is enabled on a fresh installation; existing choices are preserved on upgrade. Initial translations cover the interface, default emails and starter-guide text, and are editable. Packs were initially machine-translated with automated placeholder checks; a professional review of every language is not claimed. No content is sent to a translation service at runtime. Arabic and Hebrew pages use right-to-left direction. Administrator-authored custom content still needs its own translations.

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

Download the release's `gatearr-docker.zip`, extract it and copy `.env.example` to `.env`:

```sh
cp .env.example .env
docker compose config --quiet
docker compose pull
docker compose run --rm --no-deps gatearr python -m app.bootstrap --check
docker compose up -d --wait
```

Default image: `ghcr.io/heklalab/gatearr:latest`. Pin `:0.3.0` for a controlled version. Public container pulls require no GitHub credentials. Repository/release downloads require your GitHub login while the source repository remains private; GitHub release checks inside Gatearr also require a public repository and report an access failure while it is private.

Open `http://localhost:8000/setup`. Edit `PORT`, `BIND_ADDRESS` and `PUBLIC_URL` for your deployment. For LAN testing set `BIND_ADDRESS=0.0.0.0` and `PUBLIC_URL=http://YOUR_SERVER_IP:8000`. Ports 80/443 normally belong to your existing HTTPS proxy; Gatearr serves HTTP internally on 8000. There is no bundled Caddy or second TLS listener.

The session/encryption secret is generated once in `/data/bootstrap.json` when `SECRET_KEY` is empty. Retain it. API keys are entered in the wizard/API connections and stored encrypted, never supplied through `.env`. No installation token is required.

### Windows / Docker Desktop

```powershell
cd C:\docker-test\gatearr
Copy-Item .env.windows.example .env
docker compose pull
docker compose up -d --wait
```

The Windows example uses port 8088. Open `http://localhost:8088/setup`. For Emby on the same PC use `http://host.docker.internal:8096/emby` as the API URL. Browser/app URLs must be reachable by the actual users; another device cannot use your PC's `localhost`.

### First-run wizard

Six steps: media server/name/public URL → existing media administrator selection → optional Seerr → optional Radarr/Sonarr/Bazarr on one screen → optional SMTP → finish.

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

Set `PUBLIC_URL=https://accounts.example.com`, `COOKIE_SECURE=true`, and `TRUSTED_PROXY_IPS` to the proxy's exact address/CIDR as seen by Gatearr. If already installed, update the stored public URL in Branding too. Validate the Caddy configuration before reloading it. A formatting warning is different from a failed certificate challenge; use the actual error/status to diagnose it. `GET /healthz` and `HEAD /healthz` check application/database readiness.

## Administration

- **Branding**: identity and sign-in text, Portal builder, Themes and Footer tabs.
- **Users**: account details, email verification/invitations, direct email/password changes, reset links, groups, libraries, all media policy fields and assistance.
- **Services**: choose **Direct link** or **How to** when creating a service. The service identifier is generated automatically. How to lets you add a submenu, browser/link or tutorial; create a tutorial directly from a choice, edit its steps and publish it. Draft guides and choices remain separate from published content.
- **Emails**: SMTP and visual invitation/recovery/verification/account-change templates, localized through Translations.
- **API connections**: media server, Seerr and optional admin tools. Health indicators describe authenticated checks, separately from per-user synchronization.
- **Translations**: create a language and translate interface, content and email strings on one page. One user language applies to the interface, emails and supported Seerr settings.
- **Activity log**: time, actor, affected user, action and result. It shows readable actions, account names and selected change details (including before/after library, permission and email changes). Changes are shown by default; Show all activity also includes page visits. Passwords, API keys, session cookies and query strings are excluded. Only explicitly selected fields are recorded, never complete request bodies. Retention is 90 days, capped at 100,000 events; logs also go to the container's output.

### Account management and assistance

Administrators can send verification/reset links or directly change an email/password. Direct changes queue a localized notification; email changes notify the old and new addresses. Passwords are never emailed. Existing Gatearr sessions and recovery tokens are invalidated after direct credential changes. SMTP failures are retried by the encrypted mail outbox and recorded in container logs.

**Open portal as this user** starts an audited, 30-minute assistance session with a visible banner and return button. Gatearr account/settings writes are blocked during assistance. The user's own tools/permissions control what is displayed. Automatic Emby/Seerr links need a still-valid session created when that member previously signed in to Gatearr. If unavailable, the interface asks the member to sign in again. No user password is retained. Service links open genuine remote user sessions: actions performed there have that user's normal effects. Returning to the administrator's portal does not close already-open external browser tabs.

Emby browser login verifies the captured user token before handoff. Jellyfin web clients do not universally support this URI login scheme, so Gatearr reports the limitation instead of substituting an administrator API key.

### Media permissions and groups

Review/edit the fields actually returned by the media server: streams, downloads, subtitles, remote access and other policy settings. Authentication providers and server-maintained counters remain read-only. Sensitive administrator/disabled changes require explicit confirmation; the last active Gatearr admin is protected.

Group libraries combine. Restrictive permission flags win, and the smallest positive stream/bitrate limit wins (zero is unlimited). Conflicting structured settings require an individual override. Individual overrides take priority. Removing a membership restores original values for fields formerly managed by the group. Writes are read back; indicators distinguish confirmation, pending/drift and failures. Reading remote drift never automatically overwrites it.

Emby libraries use virtual-folder GUIDs, not numeric navigation IDs. Jellyfin uses its own adapter. Cloning copies the selected policy/configuration/home preferences through native media APIs; validate a restricted account on your actual server before granting access broadly.

### Themes, footer and icons

Only the dark theme is available in 0.2.1. Edit its palette and subtle gradient in Branding → Themes. Save a draft and publish it. Existing custom dark colors are retained; the shipped blue preset is made darker.

The footer is centered and supports one, two or three rich-text columns, links and uploaded images. Save a draft, preview it, then publish. Only the selected number of column editors is shown. Each has rich text and direct PNG/SVG image upload. Legacy content is prefilled into one editable column. Hidden columns are kept in the draft and restored when you increase the count.

Icons accept validated PNG/SVG uploads or the complete bundled Font Awesome Free 6.7.2 collection (2,060 icons across Solid, Regular and Brands) through a searchable visual picker. PNG limit: 2 MB and 1024×1024; SVG limit: 2 MB with a strict element/attribute allowlist. Scripts, embedded documents and external references are refused. Assets persist in SQLite and are served as inert images. Service icons accept uploads or Font Awesome only; external icon URL entry is removed. Font Awesome is bundled locally under its included license; no external font service is required.

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

Each tool has its own optional connection and its own user checkbox under **Admin tools**: **Admin Gatearr**, **Access Radarr**, **Access Sonarr**, **Access Bazarr**. Tool access does not require the Gatearr admin role. A tool checkbox appears after that tool is configured and enabled.

**These grants provide the complete native tool interface and its administrative actions.** They are not per-library or read-only native application roles. Gatearr checks the grant on every HTTP request and periodically during WebSocket connections; logout/revocation invalidates access.

For each tool:

1. In the native application's general settings, set **URL Base** to `/tools/radarr/app`, `/tools/sonarr/app` or `/tools/bazarr/app`, respectively. Restart the native app after changing it. Its private API and web UI will now use that prefix too.
2. In Gatearr, enter the private server root URL (for example `http://radarr:7878`) or the full prefixed private URL, plus the API key. Gatearr verifies the API under the required prefix. No public tool URL is requested.
3. Your existing main Gatearr proxy already handles the tools. No extra public hostname or Caddy site is needed. `/tools/radarr`, `/tools/sonarr` and `/tools/bazarr` show the native application inside the Gatearr interface.
4. For automatic UI login, use the native [Radarr/Sonarr external authentication setting](https://wiki.servarr.com/radarr/settings) and Bazarr proxy-only access. Keep native ports restricted to the private Docker/LAN network. Gatearr does not weaken or alter native authentication automatically. Forms authentication can otherwise show an additional login screen.
5. Gatearr administrators automatically receive every enabled tool and see it as a home-page application. For other users, grant each tool independently on the user's Gatearr page. The wrapper and every proxied HTTP/WebSocket request check the live Gatearr session and grant. Revoking the grant or signing out removes access.

The iframe shares Gatearr's browser origin. Only connect trusted native applications: this path-based arrangement is not an origin-isolation boundary, and native scripts have the same origin as the portal. Grants provide the full native interface, including administrative capabilities and configuration normally visible there. Browser cookies/Authorization/API-key headers are stripped before upstream forwarding; configured API credentials are added server-side. Arbitrary targets and redirects outside the tool prefix are refused. HTTP bodies are capped at 32 MB, WebSocket messages at 4 MB.

## Updates, backup and recovery

Back up **all of `/data`**, including `bootstrap.json`, before updating. Keep the same named volume/bind mount and the exact existing `SECRET_KEY` if supplied explicitly. Never use `docker compose down -v` to update.

```sh
docker compose pull
docker compose up -d --wait
docker compose logs --since=2m gatearr
```

Startup runs migrations automatically. See [UPGRADING.md](UPGRADING.md) before upgrading from older packages. The v0.2.0 migration removes the retired Tracearr connection secrets, queued jobs/checks and newsletter fields. Other accounts, mappings, roles, emails, Seerr/media connections and custom portal content remain.

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
