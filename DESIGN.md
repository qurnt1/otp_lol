# OTP LOL desktop visual system

## Direction contract

**THESIS:** A calm League companion that answers connection, preset, automation, and health at a glance; it refuses the crowded settings-dashboard wall.

**OWN-WORLD:** Midnight navy surfaces, warm gold for action and selection, green only for healthy connection, compact Segoe UI typography, thin cool borders, and quiet depth from layered panels rather than glow.

**STORY:** The user enters Home, sees the current client state and active preset, then moves to Presets or Automation only when configuration is needed.

**FIRST VIEWPORT:** A persistent 240px sidebar frames a wide Home canvas. The top row carries product identity and live client/rank state. The first content row gives Match Status, Active Preset, and Automation equal operational weight.

**FORM:** The selected structure is the reference-image shell: persistent navigation plus a three-column operational dashboard, extended with full pages and focused dialogs for deeper tasks. The supplied images are the visual authority.

## Durable rules

- Use a dark, blue-black desktop scene: `#0b111a` background, `#101a26` sidebar,
  `#121e2b` panels, `#1b2a3a` control surfaces, `#d0a843` action gold,
  `#3ed36b` connected green, and `#eef3f8` primary text.
- Gold is reserved for primary actions, selected navigation, and active controls.
  Green is reserved for healthy connection and successful events. Errors use a muted
  red semantic role, never decorative red.
- Prefer Segoe UI or the native Windows sans stack. Use fixed UI sizes and explicit
  hierarchy rather than fluid display typography.
- Keep the shell geometry stable: sidebar around 240px, 16px content rhythm, 8-12px
  panel radii, one-pixel borders, and compact controls with generous click targets.
- Build pages from reusable shell components: sidebar navigation, status header,
  panel header, toggle row, preset card, activity row, and toast/status feedback.
- Home is operational and concise. Preset editing, automation detail, history, and
  settings belong on dedicated pages or focused dialogs.
- Never add gradients, neon glow, decorative charts, fake metrics, or invented cloud
  features to fill space. Reference/sample data must be identifiable as preview data
  unless it comes from the runtime.
- All controls need keyboard focus, accessible names, and visible selected/disabled/
  loading/error states. State must remain understandable without color alone.
