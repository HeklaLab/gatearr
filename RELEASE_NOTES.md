Gatearr **0.2.1** fixes administration clarity, dark appearance and footer editing, and moves admin tools onto the portal hostname.

- Dark-only appearance with a darker, subtle background gradient and editable colors.
- Clear active parent/child administration navigation and consistent button spacing.
- Radarr, Sonarr and Bazarr embedded under /tools on the portal hostname, with per-request permissions.
- Footer editor shows only the selected columns, with rich text and inline PNG/SVG uploads; hidden drafts are retained.
- Hide the language selector when only one language is enabled.
- Readable audit actions, username snapshots and redacted change details.

### Updating
Back up the complete data volume and retain its encryption key, then run:
```sh
docker compose pull
docker compose up -d --wait
```
Use `ghcr.io/heklalab/gatearr:0.2.1` or `:latest` (AMD64/ARM64).

### Admin tools configuration change
Public tool hostnames are no longer used. Configure each native application's URL Base as `/tools/radarr/app`, `/tools/sonarr/app` or `/tools/bazarr/app`, restart that application, then verify its private URL/API key in Gatearr. The portal wrapper remains `/tools/radarr`, `/tools/sonarr` or `/tools/bazarr`. No extra Caddy site is required. Keep private upstream ports restricted and native proxy authentication configured as documented.

Tools now share Gatearr's browser origin. Use trusted applications and grant access deliberately: their native interfaces expose their normal full administrative capabilities. Gatearr checks the session and tool grant on every proxied request and during WebSockets; no Gatearr cookies are forwarded upstream.

Existing accounts, keys, permissions and content persist. The dark palette replaces the light appearance. Old footer items are converted into an editable rich column; no legacy editor is shown, and reducing the visible columns keeps the hidden draft content.

Automated tests and HTTP/SMTP smoke use simulators; verify actual native application versions and proxy settings on your test server.
