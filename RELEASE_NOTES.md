Gatearr **0.2.3** fixes unreadable embedded Radarr, Sonarr and Bazarr pages.

The tool proxy now forwards the original response bytes together with their Content-Encoding, including compression formats unavailable to Gatearr itself. It also replaces the browser's Accept-Encoding header correctly instead of sending conflicting duplicate values. HTML, scripts and images remain streamed; session permissions and credential isolation are unchanged.

### Update
Back up the data volume and retain its encryption key, then update the image to `ghcr.io/heklalab/gatearr:0.2.3` (or use `:latest`) and run:
```sh
docker compose pull
docker compose up -d --wait
```
Linux AMD64 and ARM64 images are published after the automated tests and Docker startup/HTTP/SMTP smoke pass. No database migration or new Radarr setting is needed for this fix. Existing native URL Base and private-upstream authentication prerequisites still apply.

Regression tests cover chunked HTML, JavaScript and binary image responses with identity, gzip, deflate, stacked and unknown encodings. Actual native server deployments have not been tested locally.
