# Gatearr 0.3.4 — public beta

## Bug fixes

- Recompute update availability against the installed version, including cached results; identical versions no longer trigger an update badge.
- Image widths set in the email builder are respected in editing, preview and saved messages.

## Interface adjustments

- Permission selections expand with the page, without nested scroll regions; library controls use the available width.
- Email template and language selectors, subject, save status and editing actions use an aligned responsive header.
- Email block deletion uses the same red danger button as the portal builder.
- Updates and feedback share the left overview column; customization reset is on the right.
- Release history shows each version once, expands only the installed version and marks it with a green current-version indicator.

## Improvements

- Reviewed interface terminology across all 21 bundled languages, with natural app wording for navigation, accounts, permissions, guides, email editing and updates; administrator overrides are preserved.

Validation: 286 automated tests, isolated HTTP/SMTP smoke and desktop/mobile browser checks. No database schema change is required when upgrading from 0.3.3. Back up /data before any upgrade.

## Upgrade

Back up the complete `/data` volume and keep its encryption key. No database schema change is required when upgrading from 0.3.3. Existing accounts, permissions, integrations, portal content and custom translations are retained.

Use `ghcr.io/heklalab/gatearr:0.3.4` (or `latest`), then run:

```sh
docker compose pull
docker compose up -d --wait
```

Images support Linux AMD64 and ARM64. Please [report bugs](https://github.com/HeklaLab/gatearr/issues/new?template=bug_report.yml) and [request features](https://github.com/HeklaLab/gatearr/issues/new?template=feature_request.yml) on GitHub.
