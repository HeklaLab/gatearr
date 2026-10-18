# Publishing Gatearr

## Initial publication

1. Create the public `gatearr` repository under the intended GitHub owner and push this source tree to `main`. Do not include live `.env` files, data volumes or backups.
2. GitHub Actions runs the tests and the isolated Docker/SMTP smoke. Only after these succeed does it publish `ghcr.io/heklalab/gatearr:edge`, plus a commit tag, for Linux AMD64 and ARM64.
3. Push a stable version tag such as `v0.1.0`. The same checks run before publishing version tags and `latest`. Prerelease tags do not advance `latest`.
4. In GitHub Packages, open the new container package's settings and make the package **Public**. Public repository visibility alone does not make a newly created container package public. Keep its source repository linked through the OCI source label.
5. Verify anonymous access from a signed-out Docker environment: `docker pull ghcr.io/heklalab/gatearr:latest`. Do not announce availability until the workflow is green and this succeeds.
6. Set `GATEARR_IMAGE=ghcr.io/heklalab/gatearr:latest` in the deployment `.env`. Use a lowercase owner. Supply `compose.yaml`, `.env.example` and `UPGRADING.md` with the release. Users need no GitHub login to pull a public package.

The workflow authenticates using GitHub's short-lived `GITHUB_TOKEN`; no Docker Hub account, registry password or media API key is required in repository secrets. Pull requests only run verification and cannot publish containers. Protect `main` and limit who can create release tags.

## Subsequent releases

Commit changes, push them, review the verification results, then create a new `vMAJOR.MINOR.PATCH` tag. A GitHub source release may be created for that tag with user-facing release notes. Changing `main` updates only `edge`; stable installations update when a stable tag passes all checks.

After backing up `/data`, users update with:

```sh
docker compose pull
docker compose up -d --wait
```

A pull downloads the image. The second command switches the running container to it. The named data volume, secret and configured integrations remain in place, and startup applies migrations. Read each release's migration notes before updating. Rolling an image back after a database migration may require restoring the matching data backup.

## Local development

```sh
docker compose -f compose.yaml -f compose.build.yaml up -d --build --wait
```

This explicit override builds `gatearr:local`; the deployment Compose never builds source automatically. `compose.demo.yaml` remains a separate isolated mock environment used by CI. There is no bundled reverse proxy.
