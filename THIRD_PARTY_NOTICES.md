# Third-party components

Gatearr remains MIT licensed. Bundled Cap components retain their upstream Apache-2.0 license; see `app/cap/core/LICENSE` and `app/static/cap/LICENSE`.

- capjs-core 0.1.6: unmodified upstream source from npm, with proof-of-work and browser instrumentation. Runtime instrumentation uses level 1; optional obfuscator and esbuild packages are not installed.
- cap-widget 0.1.58: upstream minified browser component with a small documented iframe transport adaptation for Gatearr CSP isolation; challenge generation and validation are unchanged.
- @cap.js/wasm 0.0.8: browser SHA-256 and HashWX solver assets, bundled locally.
- Node.js 24.22.1: runtime included by the Docker image; upstream license is copied alongside it.
- Service logos identify their respective applications. Tracearr and Tdarr images originate from their official repositories and are not recolored.

Cap sources: https://github.com/tiagozip/cap
Tracearr logo: https://github.com/connorgallopo/Tracearr/blob/main/apps/web/public/logo-transparent.png
Tdarr logo: https://github.com/HaveAGitGat/Tdarr/blob/master/assets/tdarr-logo.png
