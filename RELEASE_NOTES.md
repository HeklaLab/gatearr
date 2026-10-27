# Gatearr 0.4.4 — public beta

- **Branding and appearance:** upload separate logos for light and dark themes, and let visitors choose their appearance before signing in when enabled by the administrator. Existing custom logos remain supported.
- **Guides and updates:** smooth device-guide navigation and a more compact release history grouped by topic, with fixes kept by version.
- **Email:** fix the mismatch that rejected edited templates over 10,000 characters; templates support up to 50,000 characters. Improve editor spacing.
- **Integrations and permissions:** disable offline connections without revalidating saved settings; show unavailable embedded access alongside direct links; fix stretched Seerr group switches.
- **Translations:** review interface wording and fill missing translations across all 21 bundled language packs.

The email size mismatch is one possible cause of the reported Windows/Docker issue; that deployment still needs confirmation. Setup wizard layout and the Discord link are planned for 0.4.5.

## Upgrade

Back up the complete `/data` volume, including its encryption key. Update the container to `ghcr.io/heklalab/gatearr:0.4.4` (or `latest`). Existing configuration and custom logos are retained. See [upgrade instructions](https://github.com/HeklaLab/gatearr/blob/main/UPGRADING.md).
