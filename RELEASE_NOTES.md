# Gatearr 0.4.3 — public beta

A more predictable Portal builder, independent application cards and fixes for images, custom links and Tdarr.

- **Application cards:** choose direct links, embedded tools or guides per card. Unconfigured tools offer a direct URL; custom apps remain independent even when they share a native app’s name.
- **Images:** numeric px/% sizing, working alignment, a shared crop/resize editor for large uploads and saved-image previews.
- **Builder and guides:** consistent navigation and headings, fully clickable guide choices, diffuse device artwork and clearer controls. Templates are exclusive to Portal.
- **Interface:** remembered appearance, corrected spacing/color alignment, a My account watermark and cleaner widget settings. Tracearr’s widget is now Statistics, with its original logo.
- **Integrations:** corrected Tdarr hash-URL resources and safer Emby browser-opening fallback, preserving configured ports and paths.
- **Updates:** compact history grouped by release series and a roadmap shortcut.

## Upgrade

Back up the complete `/data` volume, including its encryption key. Update the container to `ghcr.io/heklalab/gatearr:0.4.3` (or `latest`). Migration 0027 preserves existing card behavior and destinations in drafts and published layouts; review your portal after upgrading. See [upgrade instructions](https://github.com/HeklaLab/gatearr/blob/main/UPGRADING.md).

Custom-link, card-behavior and image-upload reports (#4, #6, #8) are addressed. The deployment-specific Emby port report (#5) still needs reporter confirmation. Music remains on the [roadmap](https://github.com/HeklaLab/gatearr/blob/main/ROADMAP.md), without an ETA.
