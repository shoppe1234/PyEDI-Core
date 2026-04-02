# Dashboard SVG Themes & Color Scheme — Task List

## Context

The Dashboard renders one of 4 infographic themes randomly. Two themes (BlueprintTheme, TerminalTheme) have dark/black backgrounds that clash with the site's light content area and dark sidebar, creating an oppressive feel. The user wants: (1) replace the dark themes with colorful ones, (2) research programmatic theme generation without LLM, (3) research a better overall color scheme especially for the sidebar.

**Recommended execution order:** Task 3 → Task 1 → Task 2 (sidebar color first establishes the context the new themes are designed within).

---

## Task 1: Replace Dark Themes with Colorful Alternatives

**What:** Delete BlueprintTheme.tsx and TerminalTheme.tsx. Create 2 new light/colorful themes.

### New Theme A: WatercolorTheme
- **Vibe:** Soft watercolor paint washes on cream paper
- **Palette:** Rose-200, teal-200, amber-100, lavender-200, sage/green-200 — desaturated pastels
- **Background:** New `watercolor-bg` CSS class — off-white with faint colored radial gradients
- **Cards:** Rounded-2xl, semi-transparent color washes, soft tinted shadows
- **Connectors:** Soft curved lines, no hard arrows
- **CLI:** "Paper" card with watercolor accent stripe on left
- **Tips:** 2x2 pastel wash cards with organic shapes

### New Theme B: RetroArcadeTheme
- **Vibe:** Bright pixel-art / retro game UI on a LIGHT background (not dark arcade screen)
- **Palette:** Hot pink-500, electric blue-500, lime green-400, orange-500, violet-500 — bold saturated
- **Background:** New `arcade-bg` CSS class — light cream with subtle pixel-grid dots
- **Cards:** Thick 4px colored borders, step numbers as "LVL 1"–"LVL 5"
- **Connectors:** Chunky pixel-style arrows
- **CLI:** "COMMAND INPUT" panel with thick borders, monospace
- **Tips:** Bright "power-up" cards labeled "HINT 1"–"HINT 4"

### Files to modify
| File | Action |
|------|--------|
| `portal/ui/src/components/infographics/BlueprintTheme.tsx` | DELETE |
| `portal/ui/src/components/infographics/TerminalTheme.tsx` | DELETE |
| `portal/ui/src/components/infographics/WatercolorTheme.tsx` | CREATE |
| `portal/ui/src/components/infographics/RetroArcadeTheme.tsx` | CREATE |
| `portal/ui/src/components/infographics/index.tsx` | UPDATE imports, THEMES array, THEME_NAMES |
| `portal/ui/src/index.css` | ADD `watercolor-bg`, `arcade-bg`; optionally remove `blueprint-bg`, `scanline` |

### Verification
- `npx tsc --noEmit` passes
- Reload dashboard 10+ times — see all 4 themes, all light/colorful
- Click workflow steps, copy CLI commands, click tips — all work
- Playwright screenshot of each theme

---

## Task 2: Research — Programmatic Theme Generation Without LLM

**What:** Determine if a pure Python script (no LLM, no API tokens) can generate new infographic theme variations.

### Findings

**Yes, it's feasible** via template-based JSX generation. The themes are React components (~120-230 lines), not standalone SVG images. A Python script would output `.tsx` source files, not images.

**What's parameterizable (~65% of each theme):**
- Color palettes (generate harmonious sets via `colorsys` stdlib)
- Card rotations, border styles, border radii
- Background CSS patterns (from a predefined library)
- Connector arrow styles (curvature, dash, arrowhead)
- Section label styling (uppercase, spacing, font family)
- Decorative SVG blob positions and colors

**What requires pre-authored libraries (~35%):**
- The 5 workflow SVG icons (specific concepts: checkmark, clipboard, etc.) — need a library of variant sets
- Overall theme "personality" (metaphor coherence) — need predefined template families
- CSS background textures — need a curated collection

**Recommended approach:**
1. Create 4-6 "template families" (e.g., `rounded-pastel`, `geometric-bold`, `organic-soft`, `retro-sharp`)
2. Python script randomizes colors, rotations, spacing, decorations within each family
3. Uses `jinja2` templates + `colorsys` + `random` — all pip/stdlib, zero API tokens
4. Output: ready-to-use `.tsx` files + CSS class additions
5. Could yield 20-50+ distinct visual variations from 4-6 template families

**Script location:** `scripts/generate_theme.py` with `scripts/theme_templates/` directory

**Effort:** ~2-3 hours for the script, ~1-2 hours per template family

---

## Task 3: Research — Website Color Scheme (Sidebar Focus)

**What:** The sidebar is `bg-gray-900` (near-black). It creates a harsh contrast wall next to both the light content area (`bg-gray-50`) and the colorful infographics.

### Current sidebar classes (App.tsx)
```
nav:         bg-gray-900 text-gray-200
title:       text-white
nav default: hover:bg-gray-800 hover:text-white
nav active:  bg-gray-800 text-white font-medium
footer:      text-gray-500
```

### Recommendation: Light sidebar with blue accent

```
nav:         bg-white border-r border-gray-200 text-gray-600
title:       text-gray-900 font-bold
nav default: text-gray-600 hover:bg-gray-100 hover:text-gray-900
nav active:  bg-blue-50 text-blue-700 font-medium border-l-[3px] border-blue-500
footer:      text-gray-400 (status: text-green-500 / text-red-500)
```

**Why this works:**
- Eliminates dark/light clash entirely
- All 4 infographic themes (including new colorful ones) look natural next to white sidebar
- Active page is clearly indicated by blue accent bar
- Follows modern SaaS conventions (Linear, Notion, Figma)
- Only App.tsx changes — no impact to page content

### File to modify
| File | Action |
|------|--------|
| `portal/ui/src/App.tsx` | UPDATE sidebar classes (lines 35-54) |

### Verification
- Visual check on Dashboard with each infographic theme
- Click through all 8 nav pages — confirm nothing looks broken
- Playwright screenshots before/after for comparison

---

## Execution Order

1. **Task 3** — Update sidebar color scheme in App.tsx (5 min)
2. **Task 1** — Create WatercolorTheme + RetroArcadeTheme, delete old dark themes, update barrel (30-45 min)
3. **Task 2** — Research deliverable only (document findings above). Actual script is a future effort.

## Test Gate (Final)
```bash
cd ~/VS/pycoreEdi/portal/ui && npx tsc --noEmit && echo "TSC: PASS"
# Playwright screenshots of all 4 themes
# Click-through all nav pages
```
