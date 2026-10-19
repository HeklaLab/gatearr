# Gatearr

![Gatearr](app/static/gatearr-logo.png)

A self-hosted account portal for Emby and Jellyfin. Users sign in with their existing media-server account, manage their profile and open the services you publish. Administrators customize the portal with blocks, menus, PNG icons and device guides.

Python 3.12, FastAPI, Jinja, SQLAlchemy, Alembic and SQLite/WAL. One application container and one persistent volume; no bundled reverse proxy. SQLite is intended for one host and one worker on a local disk.

## Start with Docker

Download `compose.yaml` and `.env.example` from [HeklaLab/gatearr](https://github.com/HeklaLab/gatearr). You do not need the source code or a local build. In that directory:

```sh
cp .env.example .env
# The example uses ghcr.io/heklalab/gatearr:latest.
docker compose config --quiet
docker compose pull
docker compose up -d --wait
```

Open **http://localhost:8000/setup**. `PORT` changes the published HTTP port. For LAN access set `BIND_ADDRESS=0.0.0.0` and `PUBLIC_URL=http://YOUR_SERVER_IP:8000`. HTTP is appropriate for a private test network; use your existing HTTPS reverse proxy for public access.

Only the session/encryption secret can optionally be supplied through the environment. When blank, it is generated once in `/data/bootstrap.json`. **Media API keys are entered in the wizard or API connections, not in `.env`. There is no installation token.**

The first installation must be reached on a private/local access path: it is open until a server and its first administrator have been configured. CSRF and rate limiting protect form submissions; they do not establish who owns an as-yet unconfigured portal.

## Installation wizard

1. Choose the portal name and public URL. Select Emby or Jellyfin, enter the private API URL and its API key. The key is required explicitly on this first step. Gatearr verifies the server and imports its users.
2. Select an existing, active media account and confirm its existing password. This account becomes the first Gatearr administrator. No separate local account or password is created.
3. Connect Seerr, or skip.
4. Connect Tracearr, or skip.
5. Configure SMTP, or skip.
6. Finish. The wizard is then hidden and its routes return to API connections.

The steps are shown as a numbered breadcrumb. The first-admin selection is bound to the browser that established the server connection, expires after 30 minutes and cannot be claimed a second time. All subsequent users sign in with their usual media credentials. Gatearr administration is an explicit local role; media administrator status is not inherited.

## Windows / Docker Desktop

Use Linux containers. With the project in `C:\docker-test\gatearr`:

```powershell
cd C:\docker-test\gatearr
Copy-Item .env.example .env
notepad .env
```

For a same-PC test, set:

```dotenv
PORT=8088
BIND_ADDRESS=127.0.0.1
PUBLIC_URL=http://localhost:8088
COOKIE_SECURE=false
```

Set `GATEARR_IMAGE` to the published image address listed on the GitHub release. Then:

```powershell
docker compose pull
docker compose up -d --wait
docker compose logs --tail=100 gatearr
```

Open http://localhost:8088/setup. For Emby running on Windows with its default HTTP port, use **http://host.docker.internal:8096/emby** as the API URL. Enter the key in the wizard. The browser URL is **http://localhost:8096** for same-PC access. Other computers need the Windows machine's LAN address instead of `localhost`. Emby must accept connections from Docker through the Windows firewall.

## Administration

Each section has its own page and a visible back button:

- **Branding**: portal name, logo URL, sign-in text, public URL and media web link.
- **Emails**: SMTP, test delivery and WYSIWYG invitation/verification/recovery templates, including images, links and text formatting.
- **Services**: configurable links and menus, order, new-tab behavior, emoji or uploaded/remote PNG icons.
- **Users**: imported accounts, verified email invitations, Gatearr roles, one language and media-library permissions. The last active administrator cannot be removed; role changes revoke portal sessions and email tokens.
- **API connections**: connection configuration and read-only authenticated health probes. Green means the API responded with the expected authenticated response; red means unreachable/rejected/unexpected response. Hover or focus for details and check time. Results are cached for 60 seconds; use Refresh to check again. Unconfigured connections are gray.
- **Portal builder**: blocks, multiple menus, navigation position, theme and button-hover color. Drafts stay separate from the published portal.
- **Application journeys**: direct links or nested choices such as Browser / Computer / Mobile / TV, with editable guides and store links.
- **Translations**: English source text, additional languages and every interface/content/email string on one page for the selected language, with search and optional section filters. English is the only bundled language. Empty or stale translations fall back to English.

### One language per account

The account language controls Gatearr's interface and emails. It is also queued to Seerr with the verified email and managed notification preferences. Changing the language from the header, account page or member editor uses the same field. Remote updates are retried and verified; matching uses the immutable media user ID, never a guessed username or email.

**Tracearr limitation:** its current application stores interface language in the client browser/device. Its API has no per-user locale field or update endpoint. Gatearr therefore synchronizes Tracearr contact email and newsletter subscription, but cannot change Tracearr's language remotely. It does not report a language synchronization that did not happen. Seerr and Tracearr also retain their own supported translation catalogs.

User-list synchronization indicators include Seerr/Tracearr only when their connector is enabled with a URL and key. These indicators describe the latest observed per-user synchronization, separately from the API connection health check.

### Emby library access

Emby permissions use each virtual folder's **Guid**, not its numeric `ItemId`. Gatearr maps the available folders to those permission GUIDs, writes `EnableAllFolders` / `EnabledFolders`, clears obsolete subfolder exclusions and verifies the saved policy. Other policy restrictions are preserved. Jellyfin keeps its own adapter and identifiers. Test a restricted media account on your server before enabling the portal publicly.

Cloning uses the supported native APIs to copy policy, configuration and home-screen preferences from a non-administrator template. A newly created account is protected during provisioning; failures attempt to remove only that new account. Creation/copy operations across services are not a distributed transaction.

### Icons and email templates

PNG uploads support 2 MB and 1024 × 1024 pixels maximum. Image structure, CRCs, decoded-size bounds and dimensions are checked; metadata is stripped. Images are stored in SQLite, deduplicated and served with a fixed PNG content type and `nosniff`. Icons are public assets; historical icon URLs are retained after replacement.

Email templates use `${app_name}`, `${username}`, `${link}` and `${minutes}`. The invitation has its own template. HTML is allowlisted and sanitized, variables escaped, and a plain-text alternative included. Recovery/verification links expire after 30 minutes and are single use. SMTP is required for email verification and recovery. Administrators use the same account and email verification flow as other users; verify an address before using test delivery.

## Connected services

Seerr needs its URL and API key. It must already contain the matching media account. Its global email delivery must be enabled for email notifications. Gatearr preserves unrelated settings and notification agents. Notification policy can be unmanaged, user-selectable or enforced by the administrator.

Tracearr needs its URL, public API key, media-server UUID and an owner login with explicit internal-API permission. Public API v2 identifies the exact media account; the owner-only internal endpoint updates `contactEmail`, not the owner's authentication email. Newsletter opt-out uses suppression state and respects a remote unsubscribe until the user explicitly opts in again. Internal endpoints may change; validate against your version. A missing or ambiguous mapping is an error, not permission to update a different account.

## Existing reverse proxy

Connect your existing proxy container to Gatearr's Docker network or attach Gatearr to the proxy's external network. An example override:

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

Run with `docker compose -f compose.yaml -f compose.proxy.yaml up -d --wait`. In your existing Caddy configuration:

```caddyfile
accounts.example.com {
    reverse_proxy gatearr:8000
}
```

Set `PUBLIC_URL=https://accounts.example.com`, `COOKIE_SECURE=true` and `TRUSTED_PROXY_IPS` to the proxy's exact IP/CIDR as seen by the container. Update the stored public URL in Branding too if the portal was already installed. No Caddy container, certificate volume or port 443 listener is bundled. Never trust arbitrary forwarded headers on a publicly reachable application port.

## Updates and backups

Back up the complete `/data` volume, including `bootstrap.json`, before upgrading. Keep the original `SECRET_KEY` if you supplied one. Changing this key makes stored connections and queued emails unreadable. For an existing deployment that used a different service/project name, follow [UPGRADING.md](UPGRADING.md) to attach its existing volume instead of accidentally starting an empty portal.

Migrations run automatically at container startup. Revision `0010` removes the bundled French language and its translations, resets affected users to English, unifies account language and adds connection-check history. Other custom languages, users, media mappings, roles, email addresses and encrypted connections are retained. Older local-only administrator identities are retired by the historical migration; no media user is promoted implicitly.

```sh
docker compose pull
docker compose up -d --wait
docker compose logs --tail=100 gatearr
```

`pull` downloads the new image; `up -d` recreates the container while preserving `/data`. Never use `down -v` when upgrading. Pin `GATEARR_IMAGE` to a version tag for controlled upgrades. The stable `latest` tag follows version releases; `edge` follows the main development branch.

### Build from source

Developers can use the source checkout without a published image:

```sh
docker compose -f compose.yaml -f compose.build.yaml up -d --build --wait
```

See [PUBLISHING.md](PUBLISHING.md) for release and container publication.

Server-side administrator recovery, using an existing active media account:

```sh
docker compose exec gatearr python -m app.admin_cli list-users
docker compose exec gatearr python -m app.admin_cli grant-admin MEDIA_USER_ID
```

## Tests and isolated demo

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
docker compose -f compose.demo.yaml up -d --build --wait
python scripts/smoke.py
```

The demo uses simulated media/Seerr/Tracearr services and Mailpit at http://localhost:8025. At setup enter `http://mock-emby:8096/emby` and the demo key `demo-emby-key`, then choose `portal-admin` / `AdminPassword123!`. The ordinary account is `demo` / `DemoPassword123!`; the smoke test changes it to `ResetPassword123!`. Demo credentials are deliberately test-only. The demo stack is isolated and must stay private.

See [VALIDATION.md](VALIDATION.md) for executed checks and limits, and [CHANGELOG.md](CHANGELOG.md) for changes. External contracts: [Emby libraries](https://betadev.emby.media/reference/RestAPI/LibraryStructureService/getLibraryVirtualfoldersQuery.html), [Seerr user settings](https://github.com/seerr-team/seerr/blob/develop/server/routes/user/usersettings.ts), [Tracearr identity schema](https://github.com/connorgallopo/Tracearr/blob/main/packages/shared/src/schemas.ts), [Tracearr client language](https://github.com/connorgallopo/Tracearr/blob/main/packages/translations/src/language.ts).

## Version, footer and access administration

**Administration → Updates** shows the installed version/build, bundled changelog and latest GitHub release. Checks run at most every six hours and can be disabled. Administrators see an update indicator; connection failures remain visible rather than reporting a successful check. A refreshed build of the same initial version is detected using the release tag's commit reference.

**Footer** manages a global draft with text, links and uploaded PNG logos, alignment and ordering. Preview before publishing. Existing custom portal colors and journeys are preserved. Default device guides can be added from **Guides** only when no existing guides/journeys would be replaced. Their steps and store links remain editable and translatable.

**Users → user → Media-server permissions** exposes the policy returned by the connected server, including simultaneous streams and subtitle downloading. Authentication provider identifiers and server-maintained counters are read-only. Sensitive administrator/disabled changes need explicit confirmation. The adjacent status shows confirmed, pending/different, or failed readback; merely reading a remote change never overwrites it.

**Groups** applies shared policy and libraries to selected users. Library grants combine across groups. Restrictive permissions win and the smallest positive stream/bitrate limit wins (zero means unlimited). Conflicting structured settings require an explicit individual override. Individual overrides take priority; removing membership restores the original value for fields formerly managed by the group. Changes queue for application and verification. Use the user page to inspect or retry errors.

## Optional automatic Seerr login

Configure the Seerr API and public HTTPS URL in **API connections**, then enable automatic login. Existing Seerr accounts must already be imported and linked to the same media-server identity. Sign out and back in to Gatearr to prepare the Seerr session. Gatearr never retains the password or includes credentials in a link. An encrypted, temporary Seerr session is bound to the Gatearr session; the handoff ticket expires after 60 seconds and can be used once.

On the **Seerr public hostname**, route only `/gatearr-login` to Gatearr using your existing reverse proxy. For an existing Caddy Docker deployment, adapt the upstream names/ports to your shared Docker network:

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

Preserve the original Host header. Gatearr's public URL and Seerr's public URL must match their actual browser origins. Other reverse proxies need the equivalent route. No proxy is bundled. Without this opt-in configuration, the journey opens the ordinary Seerr login page. Gatearr attempts to end its captured Seerr session on logout; independently created Seerr sessions follow Seerr's own expiry rules. This integration is tested against simulators; validate your installed Seerr version and proxy before enabling it for users.
