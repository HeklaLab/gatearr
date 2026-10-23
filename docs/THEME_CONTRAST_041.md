# Theme readability review — 0.4.1

The approved capsule navigation remains the reference. The measurements below were made during the readability review. The approved Structured profile layout was subsequently integrated into the local functional demo; see ADMIN_041_REVIEW.md.

## Findings and change

Electric Lime’s original accent (#c5f52c) has only 1.27:1 contrast against white. Links, selected capsule labels and avatar initials used that fill color as text. The prior light accent-label mix was also too close to the minimum when used over tinted surfaces.

Keep vivid accents for button fills, selected backgrounds and decoration. Accent foregrounds now use the shared accent-label token: in light appearance, 35% accent and 65% text in sRGB; in dark appearance, the preset’s accent remains unchanged. The token updates immediately with live palette changes through CSS variables. Keyboard focus and small data bars use the readable color too.

Account status badges, sign-out links, success messages and warning statuses use appearance-aware semantic colors. Native headings retain the primary text color. The bundled wordmark uses black text in light appearance and white text in dark appearance, while the overlaid symbol stays colored. Custom logo images are untouched.

## Browser measurements

Real server-rendered templates were exported from isolated test data for users, user account, group editor, administration home and portal home. All six preset/appearance combinations were loaded in a browser: 30 pages and 294 visible sampled text elements. Samples include h1/h2, section eyebrows, user links, active capsules, account-active badges and help text. Computed sRGB foregrounds were compared against composited ancestor/tinted backgrounds. This is a focused readability review, not a complete accessibility certification or a guarantee for arbitrary author-selected colors, imagery or every transient UI state.

| Preset | Light minimum | Dark minimum |
| --- | ---: | ---: |
| Blue Boréal | 5.50:1 | 5.45:1 |
| Electric Lime | 5.50:1 | 8.31:1 |
| Neon Rose | 5.50:1 | 4.90:1 |

The 4.5:1 text threshold comes from [WCAG Contrast Minimum](https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html). Unit checks additionally cover text/muted colors, accent foregrounds over tinted surfaces and gradient endpoints, and button text over normal/hover fills.

Validation: full regression suite 403 passed / 1 optional review-export skipped; 13 focused checks passed after the bundled-wordmark adjustment (six palette cases, the page export and existing asset/theme coverage). Demo data, published palettes, account appearance choices and custom logos were preserved. Browser review used an isolated read-only server instead of publishing temporary themes to the demo.
