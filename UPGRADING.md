# Upgrading to 0.2.3

The embedded-tool proxy now preserves compressed responses correctly, fixing unreadable Radarr/Sonarr/Bazarr pages. Pull the new image and recreate the Gatearr container; no additional native application settings or migration are required when upgrading from 0.2.2.

# Upgrading to 0.2.2

Back up the data volume and retain its encryption key. Migration 0014 adds a Font Awesome icon choice for How to services and retains accounts, secrets and uploaded images. New service edits no longer accept external icon URLs; older icons stay visible until edited. Choose an uploaded PNG/SVG or the full visual Font Awesome Free picker instead.

Gatearr administrators now have automatic access to every enabled admin tool, matching the home-page shortcuts. Non-admin grants remain individual. The existing URL Base/native authentication prerequisites still apply; tool errors now explain rejected keys, connectivity and missing URL Base while retaining non-secret form fields.

# Upgrading to 0.2.1

Back up all of `/data` and retain its existing key. Accounts and permissions are unchanged. The dark theme is now the only appearance; its palette remains editable. The bundled dark preset becomes darker, while custom dark colors are retained.

Tools move from separate public hosts to the Gatearr hostname. Set URL Base in each native service to `/tools/radarr/app`, `/tools/sonarr/app` or `/tools/bazarr/app` and restart that service. In Gatearr, save its private server root URL and API key. The public hostname field is removed. Your existing main Gatearr proxy handles these paths; old tool subdomain sites can be retired after verifying access. Native authentication/private-network prerequisites still apply. Apps share Gatearr's browser origin and must be trusted.

Legacy footer content remains published until you save/publish the new column layout. It is prefilled into the rich editor. Hidden columns remain in the draft when reducing the visible count, and can be restored by increasing it.

# Preserve an existing Docker installation

This release uses **gatearr** consistently for the Compose service, project, database and session cookie. A service/project rename does not automatically attach an older deployment's data volume. Preserve it explicitly.

For your Windows test server:

1. Before replacing files, run `docker ps` and identify the existing portal container ID.
2. In PowerShell, from `C:\docker-test\gatearr`:

```powershell
$PreviousContainer = "PASTE_EXISTING_CONTAINER_ID"
$ContainerDetails = docker inspect $PreviousContainer | ConvertFrom-Json
$DataVolume = ($ContainerDetails[0].Mounts | Where-Object { $_.Destination -eq '/data' }).Name
Write-Output $DataVolume
```

The result must be the existing portal's named data volume. If empty, inspect the container's mounts and back up its actual bind-mounted data directory instead; do not proceed with an empty/new volume.

3. Stop the old portal and copy all of its data as a backup:

```powershell
docker stop $PreviousContainer
docker cp "${PreviousContainer}:/data" ".\backup-data"
```

4. Replace the source files with the new archive. Retain the old `.env` separately if it contains an explicitly configured `SECRET_KEY`; preserve that exact value in the new `.env`. Otherwise the existing volume's `bootstrap.json` retains the original key.
5. In the new `.env`, set your desired port/public URL and add this line using the volume name printed above:

```dotenv
GATEARR_DATA_VOLUME=YOUR_EXISTING_DATA_VOLUME
```

Remove old media connection environment entries and any installation-token entry. All media API connection settings now belong in the wizard/API connections. Already saved encrypted connection settings are retained.
6. Set `GATEARR_IMAGE` in `.env` to the published image URL from the release, then start the new service:

```powershell
docker compose config --quiet
docker compose pull
docker compose up -d --wait
docker compose logs --tail=100 gatearr
```

When the standard new database path does not exist, bootstrap locates a single existing portal SQLite database in the same volume and makes a consistent SQLite backup to the new path before migrations. The original remains available. If more than one candidate exists, startup stops rather than guessing.

Your browser will need a new login because the session cookie name changed. Revision `0010` deliberately removes the previously bundled French language and its translations; affected accounts fall back to English. Recreate any additional language in Translations. The unified user language controls interface/email and the supported Seerr synchronization; Tracearr's locale remains a client-side setting without an API.

Keep the old container and `backup-data` until the new installation is verified. Never delete the data volume as an upgrade step.

## Refreshed first release — 0.1.0

Back up `/data`, keep the same volume/secret, then pull and recreate the container even if the displayed version is already 0.1.0. The initial tag/image was replaced once at the owner's request; future releases use a new version. The Updates page also displays the build reference to distinguish these builds.

Migrations `0011` and `0012` add device journey defaults, group policy/synchronization state and temporary Seerr handoff tables. Existing guides or custom journeys are not replaced. Only the untouched former default palette is changed to the blue/cyan palette; customized themes remain. The footer starts with the existing signature until explicitly edited/published. Automatic Seerr login is disabled by default and needs the existing-proxy route described in README.md.

## 0.2.0

Keep your existing data volume/bind mount, encryption key and stored public URL. Back up the whole data directory before pulling/recreating the service. Run the storage preflight described in README if switching to a Linux bind mount.

Migration `0013` adds audit events, theme/tool preferences, assistance and tool-session records. It removes retired Tracearr connection settings, synchronization/check records and newsletter columns. A downgrade does not recover deleted integration settings; restoring them requires your pre-upgrade backup. Emby/Jellyfin and Seerr configuration, account mappings, emails, groups and custom portal content are preserved.

Admin navigation is grouped into Branding, Users and Services/How to. Existing URLs remain usable. Existing footer items still render centered until a new column layout is published. Existing custom palettes are retained. New admin tools and individual tool grants are disabled/empty by default; setup completion is not reset.

Optional tool embedding needs separate public hostnames routed through the existing reverse proxy and private upstream authentication configured as documented. No new Caddy container is installed. Re-sign into Gatearr to create the temporary user sessions used by automatic media links and assistance.
