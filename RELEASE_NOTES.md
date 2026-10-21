Gatearr **0.3.0** introduces the visual portal studio.

- One visual studio for the public sign-in page, member home and shared footer, with pointer/touch drag-and-drop, real live previews, responsive widths, nested columns, rich text and image uploads.
- Edit page and block colors, gradients, buttons and hover states directly in the studio. Move the sign-in form without removing it, use starter templates, undo/redo, autosaved drafts and explicit publication with conflict detection.
- Replace How to forms with a visual choice tree, breadcrumbs and drag-and-drop cards. Choose direct links, more choices or a guide; write and reorder rich guide steps with uploaded images, download buttons and reusable server variables.
- Keep My account after applications and enabled admin tools. Bundle original PNG logos for Emby, Jellyfin, Seerr, Radarr, Sonarr and Bazarr while preserving custom icon choices.
- Include twenty additional editable language packs, with interface, default email and starter-guide translations; English alone is enabled on a fresh installation. Existing enabled languages and overrides are preserved.
- Place authenticated connection summaries for configured services above the forms, align Emby/Jellyfin and Seerr side by side and remove translation settings from API connections.
- Preserve existing layouts, guide IDs, published snapshots, accounts, uploaded assets, encrypted connections and the compressed-response proxy fix from 0.2.3.

### Update
Back up the full data volume and retain its encryption key. Set `GATEARR_IMAGE=ghcr.io/heklalab/gatearr:0.3.0` (or use `:latest`), then:
```sh
docker compose pull
docker compose up -d --wait
```
Startup applies migration 0015, adding disabled language entries without replacing existing names, enabled states or custom translations. Existing portal and footer content is adapted when opened in the visual studio; opening the editor does not publish a replacement. No reverse proxy is bundled and no native application security setting is changed.

### Translation packs
English remains the source language. Twenty additional packs are included: Arabic, Chinese (Simplified), Czech, Danish, Dutch, Finnish, French, German, Hebrew, Italian, Japanese, Korean, Norwegian Bokmål, Polish, Portuguese (Brazil), Russian, Spanish, Swedish, Turkish and Ukrainian. Initial packs are machine-translated with placeholder validation and editable overrides; they have not had comprehensive professional linguistic review. No runtime translation service is used. Languages previously enabled by an administrator stay enabled on upgrade.

The 0.3.1 password-policy and “Translations / Labels” requests are not included in this release.

Actual Emby/Jellyfin/Seerr and native tool deployments were not used for local validation. See VALIDATION.md and the release workflow for automated tests, browser checks and container smoke results.
