# Gatearr 0.5.1 — public beta

## Improvements

- **Text editing:** Use shared font-size and colour controls, reapply colours to new selections and adjust text-block spacing.
- **Application status:** Show optional connection indicators and compact warnings, with automatic checks every minute.
- **Page links:** Choose Gatearr pages directly in buttons; links follow address changes and page permissions.

## Fixes

- Save notification emails without a link; keep action links required for invitations, verification and password recovery.
- Keep breadcrumbs through the final device and choose whether guide-page blocks appear only at the start or throughout the guide.
- Use consistent button styling and spacing; remove redundant page-creation and navigation controls.
- Restrict shared header and footer editing to their own builders; remove Accordion from the footer palette.
- Refine interface wording and complete new labels in all 21 bundled languages.

## Upgrade

Back up the complete `/data` volume, including `bootstrap.json` or your configured encryption key. Update to `ghcr.io/heklalab/gatearr:0.5.1` or `latest`.

There are no new database migrations since 0.5.0. Existing accounts, permissions, integrations, SMTP settings, uploads and draft/published layouts are preserved. Application status indicators and warnings are opt-in in the Applications block. Existing guide blocks retain their current display scope until changed. Native Tracearr access remains administrator-only.

See [upgrade instructions](https://github.com/HeklaLab/gatearr/blob/main/UPGRADING.md).
