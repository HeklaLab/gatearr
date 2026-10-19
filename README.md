# Gatearr

A customizable, self-hosted account portal for Emby and Jellyfin. Sign in with your media account, manage your account and open the services published by your administrator.

Python 3.12, FastAPI, SQLAlchemy/Alembic and SQLite/WAL. One application container and one persistent data volume. English is the source language; add languages and customize all interface, content and email text in Translations. No reverse proxy is bundled.

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

Default image: `ghcr.io/heklalab/gatearr:latest`. Pin `:0.2.0` for a controlled version. Public container pulls require no GitHub credentials. Repository/release downloads require your GitHub login while the source repository remains private; GitHub release checks inside Gatearr also require a public repository and report an access failure while it is private.

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
- **Activity log**: time, actor, affected user, action and result. It records portal page visits and mutations, assistance and proxied tool actions. No request bodies, passwords, API keys, session cookies or query strings are recorded. Retention is 90 days, capped at 100,000 events; logs also go to the container's output.

### Account management and assistance

Administrators can send verification/reset links or directly change an email/password. Direct changes queue a localized notification; email changes notify the old and new addresses. Passwords are never emailed. Existing Gatearr sessions and recovery tokens are invalidated after direct credential changes. SMTP failures are retried by the encrypted mail outbox and recorded in container logs.

**Open portal as this user** starts an audited, 30-minute assistance session with a visible banner and return button. Gatearr account/settings writes are blocked during assistance. The user's own tools/permissions control what is displayed. Automatic Emby/Seerr links need a still-valid session created when that member previously signed in to Gatearr. If unavailable, the interface asks the member to sign in again. No user password is retained. Service links open genuine remote user sessions: actions performed there have that user's normal effects. Returning to the administrator's portal does not close already-open external browser tabs.

Emby browser login verifies the captured user token before handoff. Jellyfin web clients do not universally support this URI login scheme, so Gatearr reports the limitation instead of substituting an administrator API key.

### Media permissions and groups

Review/edit the fields actually returned by the media server: streams, downloads, subtitles, remote access and other policy settings. Authentication providers and server-maintained counters remain read-only. Sensitive administrator/disabled changes require explicit confirmation; the last active Gatearr admin is protected.

Group libraries combine. Restrictive permission flags win, and the smallest positive stream/bitrate limit wins (zero is unlimited). Conflicting structured settings require an individual override. Individual overrides take priority. Removing a membership restores original values for fields formerly managed by the group. Writes are read back; indicators distinguish confirmation, pending/drift and failures. Reading remote drift never automatically overwrites it.

Emby libraries use virtual-folder GUIDs, not numeric navigation IDs. Jellyfin uses its own adapter. Cloning copies the selected policy/configuration/home preferences through native media APIs; validate a restricted account on your actual server before granting access broadly.

### Themes, footer and icons

Edit the light and dark palettes, gradients and navigation in Branding. Choose forced light/dark, automatic device appearance, or user choice. Automatic follows the browser/OS appearance preference. Drafts do not change the published portal. The old custom palette is retained when upgrading.

The footer is centered and supports one, two or three rich-text columns, links and uploaded images. Save a draft, preview it, then publish. Existing footer items are retained until you publish a column layout. Content in unused columns must be moved/cleared explicitly before reducing the column count.

Icons accept validated PNG/SVG uploads or a bundled Font Awesome selection. PNG limit: 2 MB and 1024×1024; SVG limit: 2 MB with a strict element/attribute allowlist. Scripts, embedded documents and external references are refused. Assets persist in SQLite and are served as inert images. Font Awesome is bundled locally under its included license; no external font service is required.

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

1. Enter its private URL and API key in the common setup step or API connections. The private URL must use the domain root; clear the native application's URL Base setting for this subdomain deployment.
2. Choose a separate public hostname, for example `radarr.example.com`. Prefer sibling hostnames under the portal's domain for browser cookie compatibility.
3. Point that hostname's DNS at your existing proxy and proxy **all** its requests to **Gatearr**, preserving Host:

```caddyfile
radarr.example.com, sonarr.example.com, bazarr.example.com {
    reverse_proxy gatearr:8000
}
```

4. Gatearr then proxies authenticated requests to the configured private upstream. For automatic UI login, configure [Radarr/Sonarr external authentication](https://wiki.servarr.com/radarr/faq#forced-authentication) and Bazarr proxy-only access (native authentication off). **Keep native ports restricted to the private Docker/LAN network and trusted proxy.** Never expose an unauthenticated upstream to the public internet. Gatearr does not change these upstream settings for you. If retaining native Forms login, an additional login screen can remain.
5. Grant access on the user's Gatearr page. The service opens inside the portal on its separate origin. If browser third-party-cookie rules block embedded login, use **Open in a new tab**, which creates a fresh handoff.

The proxy supports HTTP streaming and WebSockets. Browser Authorization/API-key/cookie/forwarded headers are stripped; configured upstream credentials are added server-side. Arbitrary target URLs, external redirects and unauthorized requests are refused. Web origins are isolated so native application scripts do not run on Gatearr's account/administration origin. Requests are capped at 32 MB and WebSocket messages at 4 MB. Native application settings pages may expose that application's own configuration to users granted its full interface, just as when accessing it directly.

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
