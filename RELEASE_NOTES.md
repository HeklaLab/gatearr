# Gatearr 0.4.2 — public beta

Gatearr 0.4.2 brings a more consistent glass interface, clearer application cards, personal subtitle-language preferences through Bazarr, and SMTP history for administrators.

## Interface and portal

- Shared diffuse landscapes and rounded glass surfaces across all six theme variants, with explicit animated ON/OFF switches and improved mobile layouts.
- Compact administration directory, smoother sidebar/submenu navigation, a cleaner account menu, clearer active-language selection and muted red Sign out.
- Emby/Jellyfin counts and Seerr quotas now live inside their application cards. Show or hide them in Portal builder; starter presets enable them. Existing widget settings and audiences are carried forward.
- Access media and Request new movies & series sit directly below application names. Optional promotional counts round down truthfully; Seerr quotas explain their actual periods, limits and remaining availability.
- Responsive Portal builder tools, consistent application settings and preserved stylesheet order after navigation. Access guides offer Choose another device buttons at both ends.
- Dynamic saves with feedback and preserved scroll for supported preferences.

## Personal subtitle languages through Bazarr

Administrators choose one shared Bazarr language profile, grant subtitle-selection permission to users or groups, and set their language capacity. This does not grant access to the Bazarr interface. Users manage their own choices with a counter and add/remove controls; languages already present remain selectable without warnings or duplicate native updates.

Choose free replacement, a lock for a configured number of days, or an indefinite lock until an administrator intervenes. Locks are enforced server-side. Personal removal does not delete languages from the shared profile or remove downloaded subtitles. Requested subtitles depend on availability for each title.

## Administration and integrations

- SMTP history under Activity log records new send attempts and SMTP acceptance/failure without message bodies, private links or SMTP credentials. Shortcuts are available at the bottom of Emails and the mail editor. SMTP acceptance is not proof of inbox delivery.
- User-managed or group-managed language, with Gatearr-default fallback and consistent interface/email/Seerr behavior.
- Theme colors and backgrounds refresh together; connection selection avoids fragment jumps; mouse navigation no longer leaves title outlines while keyboard focus stays visible.
- Tdarr resource/API/WebSocket routing and retry feedback are improved. Validation included an isolated native Tdarr 3.01.00 server; the actual deployment still needs its own compatibility check.

## Upgrade

Back up the complete `/data` volume, including its encryption key, before updating. Automatic migrations add SMTP history and subtitle preference/lock fields. Existing accounts, integration settings, uploaded logos and customized email templates remain in place. Legacy media/request widget settings are migrated into application-card information while retaining their audiences. New Bazarr subtitle permissions are opt-in.

See [upgrade instructions](https://github.com/HeklaLab/gatearr/blob/main/UPGRADING.md), the [full changelog](https://github.com/HeklaLab/gatearr/blob/main/CHANGELOG.md) and [validation details](https://github.com/HeklaLab/gatearr/blob/main/VALIDATION.md).

## What's next

The new [roadmap](https://github.com/HeklaLab/gatearr/blob/main/ROADMAP.md) covers memberships and paid plans, Aurora for the final release, guided media-server/reverse-proxy setup, and member invitations. It is non-exhaustive: [request a feature](https://github.com/HeklaLab/gatearr/issues/new?template=feature_request.yml) to help shape future releases.
