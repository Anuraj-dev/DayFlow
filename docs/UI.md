# Dayflow UI

Odoo 19 **product** UI, not the marketing site. Read this before changing layout, tokens, or components. Page jobs still live in `docs/PRODUCT.md`.

## Product look

Dense enterprise work views. 14px system UI. Pale canvas, white sheets, 1px borders, almost no shadow. Purple bar. Search, filters, and primary actions live in one control panel. Do not repeat the current nav item as a title under the bar. List and form are views of the same records. Mobile may substitute a compact list or kanban-like rows for a dense table.

Skip decorative cards. Do not wrap every section in a card. A form is a white sheet. A directory is a table. Use a card only if a kanban column truly needs one (320px, 8px gutters, 3px color marker).

No emoji in the UI, tests, commits, or PR text.

## Tokens

Map shadcn/vue CSS variables onto these values.

| Role | Hex |
|---|---|
| Enterprise plum (navbar, primary) | `#714B67` |
| Action teal | `#017E84` |
| Canvas | `#F8F9FA` |
| Sheet / white | `#FFFFFF` |
| Border | `#DEE2E6` |
| Muted text | `#495057` |
| Body text | `#212529` |
| Success | `#28A745` |
| Info | `#17A2B8` |
| Warning | `#FFAC00` |
| Danger | `#DC3545` |

Community purple `#71639E` is not the Dayflow primary. Use Enterprise plum.

Type: native system UI (SF / Segoe / Roboto). Desktop 14px, touch 16px, small 13px. Weights 400/500/700. Line-height 1.5. H1 28px, H2 21px, H3 ~18px.

Space: 16px page padding, 32px grid gutter, 5px form micro-gap, 24px sheet vertical padding. Buttons ~5x10px. Navbar 46px. Radius 3/4/6px.

Status always includes text, not color alone.

## Shell

- 46px full-width plum bar, white text at 90% opacity, 1px darker bottom border, square entries, 8% black hover. Keep the product navigation centered on desktop, with the Dayflow wordmark pinned left and the account menu pinned right.
- White control panel under the bar: search/filter and primary actions only. Hide it when empty. 1px `#DEE2E6` bottom border.
- Content on `#F8F9FA` with a white sheet. Form sheet max ~1400px.

## Components

Install **shadcn-vue** (CLI: `npx shadcn-vue@latest init` after Tailwind v4 + `@tailwindcss/vite`). Add button, input, label, table, tabs, badge, dropdown-menu, dialog, select, textarea, separator, avatar, breadcrumb, tooltip, checkbox, skeleton, alert, calendar, pagination, sonner. Do not use Card as page layout.

Primary button: solid plum, white text. Secondary: gray. Outline: transparent with border. Hover darkens primary.

## Motion

Short functional fades. Enter `cubic-bezier(0.05, 0.7, 0.1, 1)`. Exit `cubic-bezier(0.3, 0, 0.8, 0.15)`. No celebratory effects in MVP.

## Do not copy

Odoo marketing Caveat headlines, coral/orange illustration accents, 80px app-icon tiles, 160px promotional radii, Rainbow Man.
