Gatearr **0.2.0** reorganizes administration, adds editable light/dark themes and a rich footer, and introduces audited user assistance and individually authorized admin tools.

- Branding groups identity, portal, themes and footer. Users groups accounts and groups. Services groups direct links and **How to** choices/tutorials.
- Tracearr integration removed. The migration deletes its stored credentials, queued synchronization/check records and newsletter fields.
- Direct admin email/password changes with localized notifications; email changes notify the old and new addresses. Verification invitations and reset links remain available.
- Audited, expiring assistance mode. Genuine Emby/Seerr access uses an existing, valid member session created by a prior Gatearr login; passwords are not stored. No valid session means an explicit sign-in requirement.
- Optional Radarr, Sonarr and Bazarr interfaces, authorized separately per user under Admin tools. These grants provide full native tool capabilities. They require isolated public hostnames on the existing reverse proxy and private upstreams configured for proxy authentication; see README. No second proxy is bundled.
- Editable light/dark palettes and gradients, forced/automatic/user-selectable appearance, centered rich-text footer with 1/2/3 columns, PNG/SVG uploads and local Font Awesome icons.
- Consistent control heights, equal color columns and My account displayed as a service card.
- Safe retention of non-secret setup fields after errors; storage preflight and clearer server/DNS/proxy prerequisites.
- Activity journal with actor, affected user, result and UTC time, bounded to 90 days/100,000 events, without credentials or query strings.

### Update

Back up the complete data volume and keep its encryption key, then:

```sh
docker compose pull
docker compose up -d --wait
```

Image: `ghcr.io/heklalab/gatearr:0.2.0` or `:latest`, for Linux AMD64/ARM64. Startup applies migrations. Read UPGRADING.md for Tracearr removal and data preservation. The source repository remains private; the container is publicly pullable. GitHub release discovery cannot read private releases anonymously.

Automated checks and the isolated Docker/SMTP smoke use simulators. Confirm the actual native application versions, proxy, libraries and service logins on your test server before rollout.
