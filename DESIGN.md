---
name: OTP LOL Command Center
description: A local-first League of Legends assistant that makes automation visible and adjustable.
colors:
  ink: "#101820"
  night: "#18232d"
  panel: "#22303b"
  paper: "#f5f7f8"
  paper-panel: "#ffffff"
  gold: "#c89b3c"
  gold-bright: "#f0c567"
  blue: "#3da5ff"
  teal: "#00bfa5"
  danger: "#d94f45"
typography:
  display:
    fontFamily: "Segoe UI, Inter, system-ui, sans-serif"
    fontSize: "32px"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Segoe UI, Inter, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Segoe UI, Inter, system-ui, sans-serif"
    fontSize: "10px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.12em"
rounded:
  none: "0px"
  sm: "4px"
  md: "8px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "20px"
components:
  button-primary:
    backgroundColor: "{colors.teal}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "0 12px"
    height: "34px"
  button-quiet:
    backgroundColor: "{colors.panel}"
    textColor: "#f5f5f5"
    rounded: "{rounded.sm}"
    padding: "0 12px"
    height: "34px"

# Design System: OTP LOL Command Center

## Overview

**Creative North Star: "The Match-Ready Control Room"**

OTP LOL keeps the old desktop assistant's recognizable Garen mark, darkly/flatly palette logic, and compact operational language, then opens that control room into a web surface. The interface feels like a prepared champion-select board: state is visible, assets carry meaning, and the next choice is easy to scan. The reference capture informs the information density and slot-based composition, not its exact layout or decoration.

The dark theme is the primary play-session environment: a cool charcoal room with blue navigation, gold priority markers, and teal live status. The light theme is a paper-bright working surface using the same semantic accents and the same icon/asset hierarchy. Both themes use tonal layering and restrained borders instead of generic glass or neon effects.

**Key Characteristics:**

- A vertical command rail with the OTP LOL identity and four familiar destinations.
- Priority slots that show champions, spells, runes, skins, and state together.
- A restrained status vocabulary: teal for ready, gold for configured, red for ban or error.
- Angular, compact controls with small radii and clear keyboard focus.

## Colors

The palette is a restrained League-inspired system: cool ink and panels carry the surface, while gold, blue, teal, and red are reserved for priority and state.

### Primary

- **Live Teal** (`{colors.teal}`): connection, enabled automation, and the primary action.
- **Priority Gold** (`{colors.gold}`): configured choices, update notices, and the visual link to League's historic gold.

### Secondary

- **Signal Blue** (`{colors.blue}`): navigation, informative actions, and selected but non-destructive states.

### Tertiary

- **Ban Red** (`{colors.danger}`): ban automation, destructive actions, and errors only.

### Neutral

- **Control-Room Ink** (`{colors.ink}`): text and the deepest light-theme anchors.
- **Night Panel** (`{colors.night}`): dark-theme application shell.
- **Slate Panel** (`{colors.panel}`): dark-theme cards, toolbar layers, and controls.
- **Working Paper** (`{colors.paper}`): light-theme application background.
- **Paper Panel** (`{colors.paper-panel}`): light-theme cards and form surfaces.

**The State-First Rule.** Accent colors communicate state or action. They do not decorate inactive containers.

## Typography

**Display Font:** Segoe UI (with Inter and system sans fallbacks)

**Body Font:** Segoe UI (with Inter and system sans fallbacks)

**Character:** One workhorse sans keeps the dense control room familiar on Windows. Small uppercase labels provide orientation, while titles stay compact enough to share space with live state.

### Hierarchy

- **Display** (600, 32px, 1.1): dashboard and route titles.
- **Headline** (600, 20px, 1.2): primary section headings.
- **Title** (600, 14-16px, 1.25): champion names and control groups.
- **Body** (400, 12-13px, 1.5): explanations and status copy.
- **Label** (700, 10px, 1.2, tracked uppercase): section kickers, phase and state labels.

## Layout

The desktop shell uses a 214px command rail and a flexible content canvas. The dashboard first shows a status strip and the priority board, with the configuration column beside it and the automation rail underneath. Secondary screens reuse the same rail/header language and shift to a denser single content column where controls need more width.

At widths below 900px the right column moves below the priority board. Below 680px the command rail becomes a horizontal navigation band, slot cards stack, and action groups wrap without horizontal scrolling. Spacing follows a compact 4/8/12/20px rhythm; the first heading gets more breathing room than its supporting copy.

## Elevation & Depth

Depth comes primarily from tonal layers and thin borders. Shadows are reserved for floating search results and focused overlays, so the normal dashboard remains crisp and lightweight in both themes.

### Shadow Vocabulary

- **Floating search** (`0 18px 42px rgba(0, 0, 0, 0.24)` in dark mode, softened in light mode): champion search results and other content that escapes the document flow.

## Shapes

The interface uses square-ish control-room geometry: 4px for controls and small cards, 8px for larger grouped surfaces, and circular crops only for champion/rune imagery. Borders are 1px and tonal. No rounded container is used merely to soften a generic card.

## Components

### Buttons

- **Shape:** compact 4px corners (`{rounded.sm}`), 34px minimum height.
- **Primary:** teal action surface with dark ink text; used for save and enable actions.
- **Hover / Focus:** shift the border toward blue or brighten the teal; preserve a visible gold focus ring.
- **Secondary / Ghost:** slate or transparent tonal surface for navigation and low-risk actions.

### Chips

- **Style:** short state labels with a 1px border and a small status dot.
- **State:** teal indicates connected/enabled, muted indicates waiting/off, red is reserved for ban/error.

### Cards / Containers

- **Corner Style:** 4px for compact cards, 8px for grouped shell sections.
- **Background:** neutral panel tokens, with one cooler layer for rail/toolbars.
- **Shadow Strategy:** flat at rest; floating search gets the shadow vocabulary above.
- **Border:** 1px tonal border, never a thick accent stripe.
- **Internal Padding:** 12px for dense cards, 20px for dashboard sections.

### Inputs / Fields

- **Style:** 4px corners, tonal border, surface fill, compact 32-34px height.
- **Focus:** blue border plus a restrained translucent focus halo and the global gold keyboard ring.
- **Error / Disabled:** red border and copy for errors; muted opacity without removing labels for disabled fields.

### Navigation

The command rail uses the Garen asset and OTP LOL lockup at the top, four icon-plus-label links in the middle, and client status/version at the bottom. Active navigation uses a blue edge or tonal fill, never an oversized pill. On smaller screens it becomes a compact row while keeping the same order and labels.

### Priority Slot

Each slot is a working preview, not a decorative tile: the slot number, champion portrait, name, spell icons, rune summary, skin preview, and automation state stay grouped so the player can compare the sequence without opening settings.

## Do's and Don'ts

### Do:

- **Do** use the verified local champion, spell, rune, skin, website, Garen, and gear assets wherever the product exposes them.
- **Do** keep a readable light-theme equivalent for every dark-theme state.
- **Do** make the current phase and automation state legible in text as well as color.
- **Do** use Lucide outline icons for interface actions and real game assets for game entities.

### Don't:

- **Don't** replace OTP LOL's asset identity with emoji, generic icon tiles, or unrelated logos.
- **Don't** copy the attached template's exact composition, labels, or decorative treatment.
- **Don't** imply live League state when the LCU is disconnected.
- **Don't** add gradients, glass blur, or saturated neon merely to make the dashboard feel like a game.
