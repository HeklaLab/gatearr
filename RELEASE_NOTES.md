# Gatearr 0.5.0 — public beta

## What's new

- **Page builder:** create pages with FAQ accordions, compact titles and page menus, with independent drafts and published content.
- **Access guides:** place application guides inside editable pages, including guides for custom URL applications and optional device-navigation buttons.
- **Shared layouts:** customize the header, footer, sign-in, password recovery and My account pages, with warnings when functional blocks are removed.
- **Permissions:** use the same Everyone / Administrators / Groups selector for pages, blocks and widgets; menus respect access rights.
- **Statistics:** keep Emby and Seerr in the user row, show the Statistics widget when Tracearr is configured, and reserve the native Tracearr interface for administrators.

## Fixes and refinements

- Explain which unpublished guide blocks publication without exposing its draft.
- Preserve alignment in edited email templates, including multiline email addresses, previews and sent messages.
- Keep image alignment, saved upload previews and pixel/percentage sizing consistent.
- Keep per-card destinations and same-named custom applications independent.
- Separate page activation from publishing drafts; show relative guide URLs and flag guides unused by Home.
- Improve duplicate-address errors, page deletion/restoration and confirmed permanent deletion.
- Reset all customized content while retaining accounts, permissions, native integration settings and SMTP configuration.
- Share compact rich-text formatting controls between page content and guide steps; complete new labels and refine formatting terminology in all 21 language packs.
- Correct narrow-screen page actions, translation filters, Seerr status rows and guest-header controls. Seerr switches keep their fixed width.

## Upgrade

Back up the complete `/data` volume, including `bootstrap.json` or your configured encryption key, before updating. Use `ghcr.io/heklalab/gatearr:0.5.0` or `latest`.

Migrations 0028–0034 introduce content pages, guide-page layouts and separate page activation. Existing accounts, integration credentials, SMTP settings, uploaded assets, custom applications and draft/published content are retained. Review your pages, audiences and application destinations after upgrading. Native Tracearr access is now administrator-only; member statistics remain available through the Statistics widget.

See [upgrade instructions](https://github.com/HeklaLab/gatearr/blob/main/UPGRADING.md) and the [Page builder guide](https://github.com/HeklaLab/gatearr/blob/main/docs/page-builder.md). To roll back after migrations, restore the matching full data backup with the previous image.

## Validation

665 automated tests passed; one optional browser-review export was skipped. An isolated HTTP/SMTP laboratory passed 19 functional scenarios with all seven integrations simulated and captured 16 test messages. Browser checks covered desktop, tablet and phone widths from 320 to 1440 pixels. These checks do not replace testing against every upstream version or physical mobile device.
