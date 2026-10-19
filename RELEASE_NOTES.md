Gatearr 0.1.0 is the first public version. The initial release was refreshed in place at the owner's request on 19 October 2026 to include version tracking and the completed portal features.

### Included

- Installed version, build reference, changelog and administrator-only GitHub update notification.
- Blue/cyan theme matching the unchanged, transparent Gatearr logo.
- Global footer builder: text, links, PNG logos, order/alignment, draft preview and publication.
- Default editable Computer → Windows/Mac and Phone → Android/iPhone guides, plus Seerr journey. Existing custom journeys are preserved.
- All permissions returned by the media server can be reviewed and edited, including stream limits and subtitle downloading. Authentication providers and server-maintained login counters remain read-only.
- User groups with shared permissions and library access. Library grants combine; restrictive permissions take priority; conflicting structured settings require an explicit individual override. Group security settings such as media administrator/disabled status remain individual.
- Per-permission confirmation, pending/drift and error indicators; remote changes are observed without automatic overwriting.
- Optional automatic Seerr session handoff using a short-lived one-use POST ticket on Seerr's own origin. Enable it in API connections and add the documented `/gatearr-login` route to the **existing** reverse proxy. No second proxy is bundled. Existing Seerr users are matched by immutable media identity. Passwords are not saved or included in links.

### Install / update

Download **gatearr-docker.zip**, extract it, copy `.env.example` to `.env` (or `.env.windows.example` for a Windows test), then configure the port/public URL. Existing installations must preserve the existing volume and encryption secret; see **UPGRADING.md**.

```sh
docker compose pull
docker compose up -d --wait
```

Public image: `ghcr.io/heklalab/gatearr:latest` (also `:0.1.0`), for Linux AMD64 and ARM64. Startup runs migrations automatically. Back up `/data` before upgrading.

### Validation

Automated permission/group, handoff security, versioning and footer tests are run before publishing, together with the complete Docker/SMTP smoke using simulated media services. Native Emby/Jellyfin and Seerr deployments still need validation against the server versions and reverse-proxy configuration in use.
