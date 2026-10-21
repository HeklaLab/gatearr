# Gatearr 0.3.2

- Sign in with a username or the account email, verifying the same native media identity.

- Username editing updates the media login and queues verified Seerr display-name synchronization, with retries on failure.
- Application counts cap each row, preserve older selections across rows, and keep configured applications visible in the builder preview.
- Content reset retains legacy public application URLs; save confirmations use a contrasting green badge.

- Review fixes: clean group layouts, request quotas per user/group, optional Seerr counters and readable activity messages.
- Dedicated Access guide tab, easier page selection, pixel-sized spacing blocks and save feedback.
- Bundled application PNGs, complete desktop/mobile/TV starter guides, Seerr direct-link defaults and an explicit content reset preserving server connections.

- Access guides and safe editing of saved portal blocks without opening application links.
- One Applications & API card per application, refreshed administration navigation and live theme previews.
- Compact user tabs, single-group permission ownership, Seerr permissions and request summaries.
- Account deactivation rotates remote passwords, blocks Gatearr recovery and preserves the disabled state during imports. Reactivation allows password recovery.
- Choose the default language during setup. English can be disabled; at least one language must remain active.

Back up the persistent data volume and retain the existing SECRET_KEY before upgrading. See UPGRADING.md for migration and account-deactivation details.

Update with `docker compose pull` then `docker compose up -d --wait`. The image is `ghcr.io/heklalab/gatearr:0.3.2` (also `latest`), for AMD64 and ARM64.

Validation: 223 local automated tests, local HTTP/SMTP smoke with simulated Emby and Seerr, and browser review. The release workflow additionally runs Docker Compose smoke tests before publishing the image.
