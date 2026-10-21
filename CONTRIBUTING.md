# Help improve the public beta

Gatearr v0.3.2 is the first public beta. Bug reports, feature requests, translation corrections, documentation fixes and pull requests are welcome.

## Report a bug

Use the [bug report form](https://github.com/HeklaLab/gatearr/issues/new?template=bug_report.yml). Include Gatearr/connected-application versions, deployment platform, Docker/reverse-proxy arrangement, reproduction steps, expected/actual behavior and relevant sanitized logs/screenshots. Search existing issues first and report one problem per issue when possible.

Remove passwords, API keys, tokens, private email addresses and private domains. Do not include live `.env` files, databases or backups.

## Request a feature

Use the [feature request form](https://github.com/HeklaLab/gatearr/issues/new?template=feature_request.yml). Explain the problem, affected users, desired behavior and current workaround before proposing an implementation.

## Contribute a change

Keep pull requests focused, explain the purpose and validation. For code changes run `python -m pytest -q` and the isolated Docker smoke described in the README. Include sanitized demo screenshots for UI changes. Translation changes must preserve placeholders such as `{username}` and `${link}`. Simulator tests do not guarantee compatibility with every production application version.

When discussing Gatearr elsewhere, disclose your connection to the project, follow community rules and keep replies relevant. Gatearr is independent, not an official Emby/Jellyfin product.
