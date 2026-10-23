# Public-exposure security review — updated 23 October 2026

Scope: Gatearr's current local 0.4.0 source, authentication/recovery, privileged Emby/Jellyfin calls, native-tool proxy, session/CSRF handling, uploads, bundled dependencies and container configuration. This is a source review and regression exercise, not an independent penetration-test certification or a guarantee that the application is vulnerability-free. No production server was scanned or changed.

## Findings corrected locally

- **Compromised HTTPS trust dependency.** Certifi 2026.7.22 was affected by [GHSA-6q48-6c7w-9gw2](https://github.com/advisories/GHSA-6q48-6c7w-9gw2), a critical certificate trust-store issue. The runtime requirement is updated to 2026.10.19. Existing published images must be rebuilt and deployed to receive this correction.
- **Delayed native-account revocation for privileged portal operations.** Administrator routes now verify the linked native account on each request, rather than relying on the scheduled user refresh. Native disablement or an explicit passwordless account revokes its Gatearr sessions and recovery tokens. Native verification failure blocks administration with HTTP 503. This intentionally makes administration unavailable during a native-server outage; restore native connectivity before changing portal administration settings. Proxy HTTP requests and WebSocket authorization checks also verify native account status before passing upstream credentials; an open WebSocket is rechecked every 15 seconds.
- **Passwordless native authentication.** Login and the first-administrator claim reject blank passwords before attempting native authentication. Explicit `HasPassword: false` native responses cannot establish a portal login, even if the native server returns a token for an arbitrary supplied password. An absent field remains compatible with native responses that omit it; native password verification is still mandatory.
- **Native administrator token in browser URLs.** Opening Emby for a native administrator now opens its ordinary web login, without appending its access token. Automatic URL-based sign-in remains available for ordinary native accounts. Gatearr roles remain separate: a native administrator does not automatically gain Gatearr administration.
- **Assistance proxy boundary.** Native-tool proxies now refuse assistance sessions, preventing the read-only portal restriction from being bypassed through a full native administrative interface.
- **Ambiguous proxy paths.** Both HTTP and WebSocket paths reject dot segments, backslashes, controls and nested encoded traversal before contacting the configured upstream with its API key. Only a fixed administrator-configured upstream is supported; this finding does not constitute anonymous arbitrary-host proxy access.
- **Recovery-token referrers.** Reset and address-verification pages use `strict-origin`, preventing the token-bearing path/query from being sent in Referer headers, including to same-origin assets. Form origin checks continue to work.

Regression tests are in `tests/test_public_security.py`. No new product feature was added and no release was published in this review.

## Existing protections checked

- Server-side native API keys, encrypted stored credentials, no key in browser integration configuration; fixed upstream hosts and no automatic outbound redirects.
- Opaque random session cookies, hashed session identifiers, CSRF and origin validation, session rotation on sign-in, account-version revocation, and single-use expiring recovery tokens.
- Explicit Gatearr administration and application-access grants; native administration alone does not grant portal administration. Assistance mode blocks portal administration and portal mutations; native-tool proxies are unavailable during assistance because their full native interfaces cannot enforce a read-only session.
- Login/recovery rate limits and server-verified captcha; bounded request bodies and validated uploaded PNG/SVG assets, without arbitrary remote image imports.
- No-store responses for session pages, CSP, framing restrictions, MIME sniffing protection, and HTTPS security headers when configured for HTTPS.
- Non-root container, read-only root filesystem, dropped Linux capabilities, no-new-privileges, persistent data volume, and loopback host binding by default. These are configuration/source checks; Docker is unavailable in this environment.

## Required deployment boundaries and remaining risks

**Gatearr is a privileged service.** Its media-server API key can administer Emby/Jellyfin. If an attacker gains code execution inside Gatearr, its data volume/encryption key, or a Gatearr administrator account, native administration may be compromised. Encrypting secrets with a key stored in the same container does not prevent a compromised process from using them. Captcha is not a substitute for this trust boundary.

Before public exposure:

1. Complete installation and claim the first administrator on a private network. A fresh, uninitialized public wizard has no pre-established owner; someone who reaches it first can configure their own server and claim the installation. Keep setup private until completed.
2. Use HTTPS through a maintained reverse proxy. Set the canonical public HTTPS URL and `COOKIE_SECURE=true`; verify the actual browser cookies carry Secure and HttpOnly. Expose the proxy, not Gatearr's backend port. Configure only the actual proxy addresses in `TRUSTED_PROXY_IPS`, never `*`; forged client IPs can undermine rate limiting if proxy trust is misconfigured.
3. Apply request/body/connection limits at the public proxy. Application sign-in limits do not replace network-level denial-of-service protection. Anonymous page visits allocate sessions; sustained distributed traffic can still exhaust resources. Do not publish unneeded native backend ports.
4. Limit the container's network access to the explicitly required native services and SMTP. Protect `/data`, bootstrap secrets, backups and host/Docker access. Use distinct strong native administrator credentials and patch the host, proxy and native applications.
5. Protect administration with an additional access-layer restriction where possible (for example VPN, proxy MFA or an administrator IP allowlist). Gatearr currently has no independent MFA protection. This review does not add a new authentication feature.
6. Treat access to Radarr/Sonarr/Bazarr proxy interfaces as **full access to trusted native applications**. Their pages/scripts share Gatearr's origin. A compromised native application or stored script injection there can compromise portal sessions; iframe embedding is not isolation. A separate-origin architecture would be required to eliminate that class of risk. Grant these tools only to trusted operators.
7. Ordinary Emby automatic login still uses a user-scoped access token in a URL, as required by the current integration. This may appear in browser history and the native service/reverse-proxy logs. Suppress query-string logging, protect those logs, and require a fresh native browser login for native administrators (enforced by this correction). The token is not the server API key, but it still grants that user's native permissions.
8. Monitor authentication/audit logs and keep reliable offline backups. Database/audit retention limits do not protect against host compromise or distributed denial of service.

## Validation and limits

- Python pinned runtime dependencies: `pip-audit` found one vulnerable package before the Certifi correction; after correction it reported no known vulnerabilities and no skipped package entries at the audit time. This is a point-in-time advisory check, not proof that all dependencies are safe.
- Bundled npm packages checked against OSV: `capjs-core` 0.1.6, `cap-widget` 0.1.58, `@cap.js/wasm` 0.0.8 and `pako` 2.1.0; no known advisories were returned for those versions at the audit time. Node/base-image operating-system packages have not been container-scanned locally.
- **353 automated tests passed**, including 20 public-security regressions, with one existing deprecation warning. The isolated real HTTP/SMTP smoke also passed. Results are recorded in `VALIDATION.md`. Native services in those tests are simulated. Production Emby/Jellyfin/Seerr/Tracearr instances, real public proxy/TLS behavior, and running Docker hardening were not validated here.
- Public-exposure acceptance remains conditional on the deployment boundaries above. Do not describe this review as a guarantee of extreme security, zero risk, or a completed external penetration test.

Reference guidance: [OWASP session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html), [password recovery](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html), and [Docker security](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html).


## 23 October 2026 interface follow-up

Native profile-photo updates authenticate Gatearr users, enforce CSRF/origin checks and native preference policy, accept only bounded validated PNG/JPEG data, and send the native API key only in server-side headers to the configured upstream. Other users' photos require a live administrator check. Cache identity includes the upstream configuration and native image tag; the initial is used when no photo is available.

Group deletion checks the submitted group version and membership fingerprint, requires two explicit confirmations before deleting native users, and refuses own/administrator accounts. Linked-account permissions are preflighted before deletion; failures after remote writes are reported as potentially partial and preserve remaining members. Upstream systems do not support a distributed transaction. These checks do not make a compromised Gatearr administrator harmless: native server administration remains a high-trust capability.

Installer connection tests and SMTP tests are authenticated, rate-limited and read-only. The unauthenticated first two installation stages remain owner bootstrap operations and must be completed on a private installation before public exposure. Browser and HTTP tests used isolated local simulators; no live Emby/Jellyfin/Seerr/Tracearr production instance or Docker runtime was exercised by this follow-up.

## Publication review — 23 October 2026

The full 380-test suite and isolated HTTP/SMTP smoke passed. Python runtime and bundled CAPTCHA npm advisory scans were repeated with no known vulnerabilities returned; container OS packages remain outside the local scan. The review reconfirmed the deployment boundaries above rather than treating Captcha or encrypted-at-rest API keys as protection against a compromised administrator/process.

New group-membership review reads native permissions without queuing changes. A short-lived HMAC confirmation binds the actor/session, route, group revision, membership set, selected values, native snapshots and local permission intent. Missing, expired, tampered, cross-route and stale proofs are refused before membership changes; an unavailable required Seerr account/API blocks the review. Final application is still performed through the existing verified background synchronizers; upstream native applications do not provide a distributed transaction.

OWASP session-management and file-upload guidance was consulted for this pass. Functional and visual checks used isolated simulators and fictional accounts; live upstream, public TLS and external penetration testing are not claimed. GitHub Actions supplies the additional Docker build/health/smoke gate before publication.
