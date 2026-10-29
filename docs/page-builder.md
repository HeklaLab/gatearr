# Page builder — Gatearr 0.5.0

Open **Appearance → Page builder** to edit Pages, System pages, Header or Footer. Changes are saved as drafts. **Publish** in an editor replaces its public snapshot; it does not publish a different page or a referenced guide automatically.

## Pages and navigation

The page directory groups the required **Home page**, application **Access guides**, and **Other pages**. Home cannot be renamed, disabled or deleted and has no page-level audience restriction. Its individual blocks still follow their audiences and application permissions.

Create a blank page or start with an FAQ. Page settings define the title, relative address, description, icon/logo and access rights. A new page stays private until first publication. **Enable/Disable** in the directory controls access to its existing published content; it never publishes pending edits. Deleted pages can be restored or permanently deleted after confirmation. Published guide addresses retain their `/access/...` routes.

Navigation is a **Page menu block**, not a forced page header. Cards, tiles, lists and compact pills are available wherever that block is supported. Pages inaccessible to the current user are omitted. An optional Back button returns to the previous same-origin page, with Home as the fallback; Home itself does not offer that option. The default Home links to Help & FAQ.

## Permissions

Pages, ordinary blocks and widgets share **Everyone / Administrators / Groups** controls. Everyone includes signed-in users without a group. Otherwise, administrators and the selected groups are combined with OR: matching any selected audience grants access. Selecting no audience grants nobody access. An administrator can edit/preview a page but does not bypass its public audience.

Turning Everyone on selects all controls. Turning it off clears them. Deselecting a control while Everyone is on retains the remaining explicit selections. Manually selecting all existing groups does not include ungrouped accounts or future groups. Test visibility shows examples without changing a user's actual permissions.

Menus, direct page URLs and guide aliases enforce the published audience. Native application permissions remain an additional requirement; displaying a block does not create a native upstream account or grant upstream privileges.

## Content blocks

Use Welcome, Title, Text, Image, Button, Page menu, Columns, Logo, Divider and Spacing to compose a page. Title has no body and can insert `{page_title}`. Images support pixels/percent, alignment, saved-upload previews and the shared resize/crop tool. Text has basic rich formatting, alignment and background/border controls.

Accordion answers support basic rich text without embedded images. Each item can have an uploaded icon or Font Awesome icon, optionally enlarged in its background. Answers can be expanded in the live preview. Page text and guide instructions share compact icon formatting controls; accordion answers intentionally omit paragraph alignment.

Applications is a Home-only block. Each card retains its own destination and opening behavior. Native Emby/Seerr cards can open an access guide or a direct link. Administrator tools support direct links or embedded access; unavailable embedded access explains the missing configuration. Manually added URL applications remain independent even if their name matches a native app.

## Access guides

Access guides are editable subpages containing an **Access guide** block. Application cards open the corresponding page directly, without an intermediate directory. Surround the guide block with text, accordions or other supported blocks. Statistics and Library updates are excluded from access-guide pages.

Edit the guide/device choices using **Edit guide** on its directory row. Guide articles and the device journey have separate drafts and publication. An unpublished referenced article is identified by name/path and must be published first. Publishing a surrounding page never exposes an unpublished article draft.

The regular Button block offers **Choose another device** only on access-guide pages. Default guide pages include it above and below the guide; administrators may remove or reposition it. Ordinary buttons elsewhere remain URL buttons.

Fresh presets include the Emby access-guide page and Help & FAQ. Custom URL applications can create their own guide identity in Applications & API. Names do not determine identity: a custom app named Emby or Tracearr keeps its own guide. Existing custom guide content and addresses are retained on upgrade.

## Statistics and native Tracearr

The default user application row contains Emby and configured Seerr. When Tracearr is enabled with its API URL/key configured, a standalone **Statistics** widget appears between the user applications and administrator tools. Its period, metrics and audience remain configurable. Statistics use the linked user's identity and respect opt-out; they do not require access to Tracearr's interface.

Native Tracearr is administrator-only, like the other protected administrator tools. Existing member grants cannot open its interface. Saved native member cards are presented as administrator tools with their information moved to a standalone widget when configured; existing widgets and direct destinations are preserved. Custom URL apps named Tracearr are unaffected.

## System pages, header and footer

System pages groups Sign-in, Password recovery, New password and My account. Each has an independent draft/publication. Security-sensitive recovery forms remain required, and CAPTCHA-enabled forms show a non-interactive preview in the editor.

My account has individual functional blocks for email, password and subtitle preferences, plus optional greeting, notifications, language and profile picture. Blocks can be removed; warnings identify unavailable functions and let administrators add them back. Default layouts include all of them, and feature permissions/configuration still control their public visibility.

The shared Header has one container with configurable columns. Its default layout retains the logo, main navigation and account menu. The logo uses Identity's light/dark uploads and supports logo, text or both; text defaults to `{app_name}`. Removing navigation/account menu blocks triggers a functional warning. Upload branding assets in Identity, not the Header editor.

Footer has one editable default preset. Page templates are offered for Home; other shared/system layouts can be edited directly or restored to their defaults. Authored titles, text, page descriptions, menu labels and accordion items appear in Translations as independent resources. Interface-language selection remains English-only on a fresh installation until the administrator enables more languages.

## Resetting customized content

Reset customized content removes custom pages, archived pages and custom URL applications and restores Home, system pages, header, footer, native guides, theme/presentation, labels and email templates. It retains accounts, groups, permissions, configured native integrations and SMTP settings. Back up data and read the confirmation before using this permanent reset.
