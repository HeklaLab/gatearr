# Gatearr 0.6.0 — public beta

## Improvements

- **Themes:** Six new light and dark themes with matching Gatearr logos and a visual preset gallery.
- **Text editing:** Insert guide and email variables at the cursor with convenient buttons.

## Fixes

- Keep theme previews separate from saved palettes and prevent overlapping theme saves.
- Preserve the selected appearance mode when applying and publishing a theme.

## Upgrade

Back up the complete `/data` volume, including `bootstrap.json` or your configured encryption key. Update to `ghcr.io/heklalab/gatearr:0.6.0` or `latest`. No new database migrations are required. Existing custom logos, settings and content are preserved.

See [upgrade instructions](https://github.com/HeklaLab/gatearr/blob/main/UPGRADING.md).
