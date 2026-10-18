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
