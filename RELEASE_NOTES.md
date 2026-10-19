Gatearr **0.2.2** fixes interface clarity, service icons and tool connection feedback.

- Increase button and navigation contrast and align service fields and user invitation controls.
- Replace text-only icon lists with a searchable visual picker for all 2,060 bundled Font Awesome Free 6.7.2 icons, including Solid, Regular and Brands.
- Remove external icon URL input from services and How to choices; keep PNG/SVG uploads and validated Font Awesome selections.
- Fix tool connection diagnostics, accept private root or prefixed URLs and ignore incomplete disabled optional tools. Preserve safe form fields on error without exposing API keys.
- Show every enabled Radarr, Sonarr and Bazarr application to Gatearr administrators automatically, including custom portals without service blocks. Member tool grants remain independent.

### Update
Back up the full data volume and retain its encryption key, then:
```sh
docker compose pull
docker compose up -d --wait
```
Image: `ghcr.io/heklalab/gatearr:0.2.2` or `:latest`, for Linux AMD64/ARM64. Startup applies the service-icon migration without changing accounts or credentials. Existing image uploads remain available. Old remote service icons remain visible until that service is edited; new edits accept only uploaded images or Font Awesome Free.

### Radarr, Sonarr and Bazarr
The native application's URL Base must still be `/tools/radarr/app`, `/tools/sonarr/app` or `/tools/bazarr/app`, followed by a native app restart. Enter either its private server root or that prefixed URL in Gatearr. If the root API works but URL Base is missing, Gatearr now explains this directly rather than displaying “Invalid value”. Rejected keys and unreachable servers also have explicit messages. No native security setting is changed automatically.

Admins can access all enabled tools; other users retain their individual grants. Tools remain under the Gatearr hostname with the documented native-authentication and trusted-application prerequisites. Test the actual native versions and proxy on your server; automated tests and Docker smoke use simulators.
