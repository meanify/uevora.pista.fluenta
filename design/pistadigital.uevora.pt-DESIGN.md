---
version: alpha
name: Pistadigital
description: |
  PISTA Digital embodies a professional, institutional approach to sustainable
  tourism intelligence. The design conveys authority and accessibility through a
  restrained, functional aesthetic rooted in Portugal's regional tourism
  context. Deep navy blues dominate the brand identity, paired with an energetic
  golden accent that punctuates key interactions and draws attention to calls to
  action. The visual language emphasizes clarity and data-driven
  decision-making, with generous white space, sharp geometry (flat design with
  no rounded corners), and typographic hierarchy that guides users through
  complex information. Hero imagery—outdoor activity and natural
  landscapes—anchors the emotional core, while the overall composition remains
  minimal and grid-conscious, avoiding decoration in favour of legibility and
  usability.
source:
  url: "https://pistadigital.uevora.pt/"
  pagesAnalyzed: 1
  extractedAt: 2026-10-24
  tokensMeasured: true
colors:
  primary: "#001F44"
  accent: "#FFAD00"
  link: "#2066BC"
  canvas: "#FFFFFF"
  on-primary: "#FFFFFF"
  ink: "#1D2127"
  hairline: "#4E4F50"
  neutral-1: "#000000"
  neutral-2: "#CED4DA"
typography:
  display-lg:
    fontFamily: Montserrat
    fontSize: 40px
    fontWeight: 400
    lineHeight: 1.2
    letterSpacing: 0px
  display-lg-strong:
    fontFamily: Montserrat
    fontSize: 40px
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: 0px
  heading-md:
    fontFamily: Montserrat
    fontSize: 28px
    fontWeight: 400
    lineHeight: 1.2
    letterSpacing: 0px
  heading-md-strong:
    fontFamily: Montserrat
    fontSize: 28px
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: 0px
  heading-sm:
    fontFamily: Montserrat
    fontSize: 24px
    fontWeight: 400
    lineHeight: 1.2
    letterSpacing: 0px
  heading-xs:
    fontFamily: Montserrat
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.2
    letterSpacing: 0px
  body-xl:
    fontFamily: Montserrat
    fontSize: 24px
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: 0px
  body-lg:
    fontFamily: Montserrat
    fontSize: 18px
    fontWeight: 300
    lineHeight: 1.5
    letterSpacing: 0px
  body-lg-strong:
    fontFamily: Montserrat
    fontSize: 18px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0px
  body-md:
    fontFamily: Montserrat
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0px
  body-md-strong:
    fontFamily: Montserrat
    fontSize: 16px
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: 0px
  body-sm:
    fontFamily: Montserrat
    fontSize: 14px
    fontWeight: 700
    lineHeight: 1.5
    letterSpacing: 0.6px
    textTransform: uppercase
  button:
    fontFamily: Montserrat
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0px
  caption-md:
    fontFamily: Montserrat
    fontSize: 12.8px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0px
  caption-sm:
    fontFamily: Montserrat
    fontSize: 12px
    fontWeight: 700
    lineHeight: 1.5
    letterSpacing: 0.6px
    textTransform: uppercase
  caption-xs:
    fontFamily: Montserrat
    fontSize: 11px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0px
rounded:
  none: 0px
  full: 9999px
spacing:
  xxs: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 20px
  xl: 28px
  xxl: 32px
  xxxl: 40px
  section: 48px
  band: 64px
borderWidths:
  thin: 1px
shadows:
  sm: "rgba(0, 0, 0, 0.15) 0px 2px 4px 0px"
  md: "rgba(0, 0, 0, 0.176) 0px 8px 16px 0px"
elevationStrategy: progressive
themes:
  derived: dark   # the other theme is the site's measured palette
  light:
    bg: "#FFFFFF"
    surface: "#F7F7F7"
    surfaceRaised: "#EEEEEF"
    text: "#1D2127"
    textMuted: "#6C6F73"
    border: "#4E4F50"
    accent: "#001F44"
    accentFg: "#FFFFFF"
    focusRing: "#001F44"
    elevation: shadow
  dark:
    bg: "#0C0F12"
    surface: "#1B1D20"
    surfaceRaised: "#27292C"
    text: "#F5F6F8"
    textMuted: "#9C9EA1"
    border: "#333538"
    accent: "#117DFF"
    accentFg: "#0B0B0C"
    focusRing: "#0060D3"
    elevation: "border+surface"
gradients:
  - context: hero
    kind: linear
    value: "linear-gradient(0deg, rgb(0, 31, 68) 0%, rgba(240, 240, 240, 0) 100%)"
components:
  button-icon:
    typography: "{typography.body-md}"
    textColor: "{colors.on-primary}"
    border: "1px solid {colors.primary}"
    height: 50px
    padding: "12px 12px 12px 12px"
    backgroundColor: "{colors.primary}"
  button-outline:
    textColor: "{colors.hairline}"
    border: "1px solid {colors.hairline}"
    height: 47px
    padding: "12px 24px 12px 24px"
    fontSize: 12px
    fontFamily: Montserrat
    fontWeight: 400
    lineHeight: 1.5
  button-text:
    typography: "{typography.button}"
    textColor: "{colors.primary}"
    height: 33.8281px
    padding: "6px 12px 6px 12px"
  card:
    typography: "{typography.body-md}"
    textColor: "rgb(33, 37, 41)"
    padding: "28px 28px 28px 28px"
    backgroundColor: "rgba(255, 255, 255, 0.9)"
  card-lg:
    typography: "{typography.body-md}"
    textColor: "rgb(33, 37, 41)"
    boxShadow: "rgba(0, 0, 0, 0.15) 0px 2px 4px 0px"
    backgroundColor: "{colors.canvas}"
  badge-icon:
    typography: "{typography.button}"
    textColor: "{colors.link}"
    height: 24px
  badge-icon-2:
    textColor: "{colors.on-primary}"
    height: 24px
    fontSize: 32px
    fontFamily: FontAwesome
    fontWeight: 400
    lineHeight: 0.75
  navigation:
    typography: "{typography.button}"
    textColor: "{colors.on-primary}"
    height: 85px
    padding: "10px 20px 10px 20px"
    backgroundColor: "{colors.primary}"
  footer:
    typography: "{typography.body-md}"
    textColor: "{colors.on-primary}"
    backgroundColor: "{colors.primary}"
  link:
    typography: "{typography.body-md}"
    textColor: "{colors.on-primary}"
  link-sm:
    typography: "{typography.button}"
    textColor: "rgba(255, 255, 255, 0.5)"
    padding: "8px 8px 8px 8px"
states:
  link-active:
    target: link
    state: active
    boxShadow: none
  other-hover:
    target: other
    state: hover
    textColor: "rgb(108, 117, 125)"
  button-hover:
    target: button
    state: hover
    textColor: "rgb(69, 69, 69)"
    borderColor: "rgb(197, 197, 197)"
    borderWidth: 1px
    backgroundColor: "rgb(246, 246, 246)"
  other-focus:
    target: other
    state: focus
    borderColor: currentcolor
  link-hover:
    target: link
    state: hover
    textColor: "{colors.on-primary}"
  link-focus:
    target: link
    state: focus
    outline: none
  button-focus:
    target: button
    state: focus
    outline: "-webkit-focus-ring-color auto 5px"
    outlineColor: -webkit-focus-ring-color
    outlineWidth: 5px
  other-disabled:
    target: other
    state: disabled
    opacity: 1
    backgroundColor: "rgb(233, 236, 239)"
  input-disabled:
    target: input
    state: disabled
    textColor: "rgba(29, 33, 39, 0.7)"
  input-focus:
    target: input
    state: focus
    boxShadow: "rgba(40, 167, 69, 0.25) 0px 0px 0px 0px"
    borderColor: "rgb(40, 167, 69)"
  button-disabled:
    target: button
    state: disabled
    opacity: 0.65
    boxShadow: none
  button-active:
    target: button
    state: active
    boxShadow: "rgba(0, 0, 0, 0.125) 0px 3px 5px inset"
  other-active:
    target: other
    state: active
    textColor: "{colors.on-primary}"
    textDecoration: none
    backgroundColor: "{colors.primary}"
  input-active:
    target: input
    state: active
    textColor: "{colors.on-primary}"
    boxShadow: none
    borderColor: "rgb(0, 112, 247)"
    backgroundColor: "rgb(0, 112, 247)"
breakpoints:
  - width: 375
    containerWidth: 1920
    gridColumns: 0
    navLinksVisible: 1
    menuToggleVisible: true
    headingPx: 28
    bodyPx: 16
    sectionPaddingX: 0
  - width: 768
    containerWidth: 1920
    gridColumns: 0
    navLinksVisible: 1
    menuToggleVisible: true
    headingPx: 34
    bodyPx: 16
    sectionPaddingX: 0
  - width: 1024
    containerWidth: 1920
    gridColumns: 3
    navLinksVisible: 10
    menuToggleVisible: true
    headingPx: 37
    bodyPx: 16
    sectionPaddingX: 0
  - width: 1280
    containerWidth: 1920
    gridColumns: 3
    navLinksVisible: 10
    menuToggleVisible: true
    headingPx: 40
    bodyPx: 16
    sectionPaddingX: 0
  - width: 1440
    containerWidth: 1920
    gridColumns: 7
    navLinksVisible: 10
    menuToggleVisible: true
    headingPx: 40
    bodyPx: 16
    sectionPaddingX: 0
coverage:
  statesFound: 61
  gradientsFound: 1
  rolesUnassigned: 2
  archetypesUnnamed: 0
  archetypesDetected: 0
  responsiveMeasured: true
  stylesheetsBlocked: false
  semanticRampDeclared: false
---

# Design System Inspired by PISTA Digital

## 1. Visual Theme & Atmosphere

PISTA Digital embodies a professional, institutional approach to sustainable tourism intelligence. The design conveys authority and accessibility through a restrained, functional aesthetic rooted in Portugal's regional tourism context. Deep navy blues dominate the brand identity, paired with an energetic golden accent that punctuates key interactions and draws attention to calls to action. The visual language emphasizes clarity and data-driven decision-making, with generous white space, sharp geometry (flat design with no rounded corners), and typographic hierarchy that guides users through complex information. Hero imagery—outdoor activity and natural landscapes—anchors the emotional core, while the overall composition remains minimal and grid-conscious, avoiding decoration in favour of legibility and usability.

**Key Characteristics**
- Deep navy primary (`{colors.primary}` — `#001F44`) as the dominant brand colour
- Golden accent (`{colors.accent}` — `#FFAD00`) for highlights and secondary emphasis
- Sharp, rectilinear design (0px border radius throughout)
- Single-weight typography (Montserrat 400) with deliberate heavy weights (700) for contrast
- Flat surfaces with minimal shadow depth; colour blocking over layering
- Institutional, data-forward tone suitable for government/tourism authority content
- No rounded corners; all interactive elements are rectangular or pill-shaped (9999px only)
- High contrast text on solid backgrounds; minimal transparency effects

## 2. Color Palette & Roles

### Primary
- **Brand / Primary CTA** (`{colors.primary}` — `#001F44`): Deep navy used across primary buttons, navigation bar, footer, active states, and all brand-critical UI. Creates strong, authoritative presence.
- **Primary Accent** (`{colors.accent}` — `#FFAD00`): Warm golden yellow applied to hero bands, secondary navigation highlights, and decorative elements that break the navy monotone.

### Interactive
- **Link** (`{colors.link}` — `#2066BC`): Medium blue for inline hyperlinks, distinct from the brand navy to signal interactive text.

### Neutral Scale
- **Canvas** (`{colors.canvas}` — `#FFFFFF`): Default page background; used for all card surfaces and primary text containers. Also serves as label colour on brand surfaces (navigation, footer).
- **Ink** (`{colors.ink}` — `#1D2127`): Primary heading and body text colour; near-black for maximum contrast and readability.
- **Hairline** (`{colors.hairline}` — `#4E4F50`): Subtle medium-grey for 1px borders, dividers, and secondary text.

### Surface & Borders
- **Neutral Decorative** (`{colors.neutral-1}` — `#000000`): Pure black, role unassigned; appears in limited decorative contexts.
- **Neutral Decorative** (`{colors.neutral-2}` — `#CED4DA`): Light grey, role unassigned; used for subtle background fills or disabled states in forms.

## 3. Typography Rules

### Font Family
**Primary:** Montserrat (https://fonts.googleapis.com/css?family=Montserrat:300,300i,400,400i,700,700i&display=swap)
Fallback stack: `Montserrat, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`

### Hierarchy

| Role | Font | Size | Weight | Line Height | Letter Spacing | Notes |
|---|---|---|---|---|---|---|
| **Display Large** | Montserrat | 40px | 400 | 1.2 | 0px | Hero headings; h2 level |
| **Display Large Strong** | Montserrat | 40px | 700 | 1.2 | 0px | Bold hero/display contexts |
| **Heading Medium** | Montserrat | 28px | 400 | 1.2 | 0px | Section headings; h3 level |
| **Heading Medium Strong** | Montserrat | 28px | 700 | 1.2 | 0px | Bold section headings |
| **Heading Small** | Montserrat | 24px | 400 | 1.2 | 0px | Subsection headings; h4 level |
| **Heading Extra Small** | Montserrat | 16px | 400 | 1.2 | 0px | Tertiary headings; h6 level |
| **Body Large** | Montserrat | 18px | 300 | 1.5 | 0px | Light body copy; introductory text |
| **Body Large Strong** | Montserrat | 18px | 400 | 1.5 | 0px | Standard body emphasis |
| **Body Extra Large** | Montserrat | 24px | 700 | 1.2 | 0px | Bold body callouts |
| **Body Medium** | Montserrat | 16px | 400 | 1.5 | 0px | Standard body copy |
| **Body Medium Strong** | Montserrat | 16px | 700 | 1.2 | 0px | Bold inline or list text |
| **Body Small** | Montserrat | 14px | 700 | 1.5 | 0.6px | Uppercase labels; navigation items |
| **Button** | Montserrat | 14px | 400 | 1.5 | 0px | Standard button text |
| **Caption Medium** | Montserrat | 12.8px | 400 | 1.5 | 0px | Small supporting text; metadata |
| **Caption Small** | Montserrat | 12px | 700 | 1.5 | 0.6px | Uppercase captions; badges |
| **Caption Extra Small** | Montserrat | 11px | 400 | 1.5 | 0px | Minimal supporting text |

### Principles
- **Minimalist weight distribution:** 300 and 400 weights for breathing room; 700 reserved for emphasis and hierarchy breaks.
- **Generous line height on body:** 1.5 across all body and button sizes for legibility; headings compress to 1.2 for visual density.
- **Uppercase tracking:** Small labels and captions gain `letter-spacing: 0.6px` and `text-transform: uppercase` to create visual distinction without size change.
- **No letter-spacing on display:** Large headings remain at 0px, relying on size alone for presence.
- **Single font family:** Montserrat throughout; no serif transitions. Consistency reinforces institutional character.

## 4. Component Stylings

### Buttons

**Primary Button**
- Background: `{colors.primary}` (`#001F44`)
- Text: `{colors.canvas}` (`#FFFFFF`)
- Padding: `{spacing.sm}` `{spacing.md}` `{spacing.sm}` `{spacing.md}` (12px 16px 12px 16px)
- Border Radius: `{rounded.none}` (0px)
- Border: `1px solid {colors.primary}` (`#001F44`)
- Font: `{typography.button}` (14px, weight 400, line-height 1.5)
- Hover: Background `#007FFF`, text `#FFFFFF`, border `#007FFF`; box-shadow `rgba(0, 31, 68, 0.25) 0px 0px 0px 0px`
- Active: Box-shadow `rgba(0, 31, 68, 0.25) 0px 0px 0px 0px, rgba(0, 0, 0, 0.125) 0px 3px 5px inset`
- Focus: Box-shadow `rgba(0, 31, 68, 0.25) 0px 0px 0px 0px`
- Disabled: Opacity 0.65; box-shadow none

**Secondary Button (Outline)**
- Background: transparent
- Text: `{colors.hairline}` (`#4E4F50`)
- Padding: `{spacing.sm}` `{spacing.md}` `{spacing.sm}` `{spacing.md}` (12px 24px 12px 24px)
- Border Radius: `{rounded.none}` (0px)
- Border: `1px solid {colors.hairline}` (`#4E4F50`)
- Font: `{typography.caption-sm}` (12px, weight 400, line-height 1.5, letter-spacing 0.6px, uppercase)
- Hover: Background `#F6F6F6`, text `#454545`, border `#C5C5C5`
- Focus: Outline none; outline-width 0px
- Disabled: Opacity 0.65; box-shadow none

**Ghost Button (Text)**
- Background: transparent
- Text: `{colors.primary}` (`#001F44`)
- Padding: `{spacing.xs}` `{spacing.sm}` `{spacing.xs}` `{spacing.sm}` (6px 12px 6px 12px)
- Border Radius: `{rounded.none}` (0px)
- Border: none
- Font: `{typography.button}` (14px, weight 400, line-height 1.5)
- Hover: Text `#154373` (darker navy); text-decoration underline
- Focus: Text-decoration underline; outline none
- Disabled: Text `#6C757D`

**Button with Icon (Primary)**
- Background: `{colors.primary}` (`#001F44`)
- Icon: `{colors.canvas}` (`#FFFFFF`)
- Padding: `{spacing.sm}` (`12px 12px 12px 12px`)
- Border Radius: `0px 2px 2px 0px` (rounded right corners only)
- Border: `1px solid {colors.primary}` (`#001F44`)
- Icon Size: 16px
- Height: 50px
- Width: 41px
- Font: `{typography.body-md}` (16px, weight 400)

### Cards & Containers

**Card Default**
- Background: `rgba(255, 255, 255, 0.9)` (semi-transparent white)
- Text: `#212529`
- Padding: `{spacing.xl}` (28px all sides)
- Border Radius: `{rounded.none}` (0px)
- Border: none
- Box Shadow: none
- Width: 378px (fixed)
- Height: 356.188px (fixed)
- Font: `{typography.body-md}` (16px, weight 400, line-height 1.5)

**Card Large (with Elevation)**
- Background: `{colors.canvas}` (`#FFFFFF`)
- Text: `#212529`
- Padding: 0px all sides
- Border Radius: `{rounded.none}` (0px)
- Border: `0px solid rgba(0, 0, 0, 0.125)`
- Box Shadow: `rgba(0, 0, 0, 0.15) 0px 2px 4px 0px`
- Width: 378px (fixed)
- Height: 605.984px (fixed)
- Font: `{typography.body-md}` (16px, weight 400, line-height 1.5)

### Inputs & Forms

**Input Focus State**
- Border Color: `#001F44` (`{colors.primary}`)
- Box Shadow: `rgba(0, 31, 68, 0.25) 0px 0px 0px 0px`
- Background: `{colors.canvas}` (`#FFFFFF`)

**Input Disabled State**
- Background: `#E9ECEF` (light grey)
- Text: `rgba(29, 33, 39, 0.7)` (muted ink)
- Cursor: not-allowed

**Input with Validation Focus (Success)**
- Border Color: `#28A745` (green)
- Box Shadow: `rgba(40, 167, 69, 0.25) 0px 0px 0px 0px`

**Input with Validation Focus (Error)**
- Border Color: `#DC3545` (red)
- Box Shadow: `rgba(220, 53, 69, 0.25) 0px 0px 0px 0px`

### Navigation

**Header Navigation**
- Background: `{colors.primary}` (`#001F44`)
- Text: `{colors.canvas}` (`#FFFFFF`)
- Padding: `{spacing.sm}` `{spacing.lg}` `{spacing.sm}` `{spacing.lg}` (10px 20px 10px 20px)
- Border Radius: `{rounded.none}` (0px)
- Border: none
- Font: `{typography.button}` (14px, weight 400, line-height 1.5)
- Height: 85px
- Width: 100% (responsive, max 1440px)
- Link Hover: Text `#FFFFFF`; background `rgba(0, 0, 0, 0.08)`; box-shadow none
- Link Active: Text `#FFFFFF`; background `#001F44`; text-decoration none

### Footer

**Footer Default**
- Background: `{colors.primary}` (`#001F44`)
- Text: `{colors.canvas}` (`#FFFFFF`)
- Padding: 0px all sides
- Border Radius: `{rounded.none}` (0px)
- Border: none
- Font: `{typography.body-md}` (16px, weight 400, line-height 1.5)
- Height: 640.234px (measured full height)
- Width: 100% (responsive, max 1440px)

**Footer Link (Default)**
- Text: `{colors.canvas}` (`#FFFFFF`)
- Font: `{typography.body-md}` (16px, weight 400, line-height 1.5)
- Background: transparent
- Padding: 0px
- Border: none
- Hover: Text `#FFFFFF`; box-shadow none; text-decoration none

**Footer Link (Dimmed)**
- Text: `rgba(255, 255, 255, 0.5)`
- Font: `{typography.button}` (14px, weight 400, line-height 1.5)
- Padding: `{spacing.xs}` (8px all sides)
- Background: transparent
- Hover: Text `#FFFFFF`; background `rgba(255, 255, 255, 0.075)`

### Badges

**Badge Icon**
- Background: transparent
- Text: `#2066BC` (`{colors.link}`)
- Padding: 0px
- Border Radius: `{rounded.none}` (0px)
- Border: none
- Font: `{typography.button}` (14px, weight 400, line-height 1.5)
- Width: 26px
- Height: 24px

**Badge Icon Secondary (FontAwesome)**
- Background: transparent
- Text: `{colors.canvas}` (`#FFFFFF`)
- Padding: 0px
- Border Radius: `{rounded.none}` (0px)
- Border: none
- Font: FontAwesome, 32px, weight 400, line-height 1.5
- Width: 27px
- Height: 24px

## 5. Layout Principles

### Spacing System
Base unit: `{spacing.xs}` = 8px. All spacing scales in increments:
- `{spacing.xxs}` = 4px (micro-adjustments, rarely used)
- `{spacing.xs}` = 8px (tight padding within small components)
- `{spacing.sm}` = 12px (default button padding, input padding)
- `{spacing.md}` = 16px (standard padding, medium margins)
- `{spacing.lg}` = 20px (generous component spacing)
- `{spacing.xl}` = 28px (card padding, section spacing)
- `{spacing.xxl}` = 32px (large section padding)
- `{spacing.xxxl}` = 40px (hero spacing, large gaps)
- `{spacing.section}` = 48px (between major content blocks)
- `{spacing.band}` = 64px (full-width hero or section separation)

**Usage Context:**
- Buttons: `{spacing.sm}` vertical, `{spacing.md}` horizontal padding
- Cards: `{spacing.xl}` (28px) all-around padding
- Section margins: `{spacing.section}` (48px) or `{spacing.band}` (64px) between blocks
- Navigation bar: `{spacing.sm}` `{spacing.lg}` padding (compact yet breathable)

### Grid & Container
- **Max Width:** 1920px (measured; full-width content column)
- **Column Strategy:** Flexible layout; not a rigid multi-column grid on mobile. At 375px and 768px, content is single-column (1 column). At 1024px+, layout expands to approximately 3–7 logical columns (not a CSS Grid specification but a content distribution pattern).
- **Section Patterns:** Full-width hero bands with overlay darkening (`linear-gradient(0deg, #001F44 0%, rgba(240, 240, 240, 0) 100%)`); white content sections with cards arranged horizontally at wider viewports; footer spans full width.

### Whitespace Philosophy
Generous and intentional. The system favours breathing room over density; headings and paragraphs are separated by at least `{spacing.md}` (16px). Cards use `{spacing.xl}` (28px) internal padding, creating clear visual boundaries. Section separation is `{spacing.section}` (48px) or more, preventing visual clutter. Inactive space is not filled with decoration; instead, colour blocking and scale hierarchy establish information hierarchy.

### Border Radius Scale
Only two values exist in the system:
- `{rounded.none}` = 0px — all rectangular components (buttons, cards, inputs, navigation, footer, badges)
- `{rounded.full}` = 9999px — pill-shaped elements (rare; primarily decorative or specialized interactive states)

The system is predominantly sharp and rectilinear. Pill-shaped elements are exceptions, not defaults.

### Border Widths
Only one width is in active use:
- **Thin** = 1px — applied to button borders (outline and primary variants), input borders, and card borders. Creates visual definition without visual weight.

## 6. Depth & Elevation

| Level | Treatment | Use |
|---|---|---|
| **Flat (Base)** | No shadow; solid colour | Default cards, buttons, navigation, footer, page background |
| **Raised (Micro)** | `rgba(0, 0, 0, 0.15) 0px 2px 4px 0px` | Cards with subtle lift; small elevated surfaces |
| **Elevated (Subtle)** | `rgba(0, 0, 0, 0.176) 0px 8px 16px 0px` | Dropdown menus, modals, overlays |

**Shadow Philosophy:**
The design system employs a **progressive** elevation strategy based on colour blocking rather than shadow layering. The majority of surfaces are flat (no shadow). Raised surfaces use a single, minimal shadow to create barely-perceptible lift. Only the deepest surfaces (dropdowns, modals) receive increased shadow depth. Emphasis comes from colour contrast and spatial positioning, not shadow density. This keeps the interface clean and prevents shadow pollution.

### Opacity Levels
- **50% (0.50)** — Applied to semi-transparent overlays, disabled states, and text dimming. Used on card backgrounds (`rgba(255, 255, 255, 0.9)`) to create subtle depth within a band.

### Z-index / Layering
The stacking order follows a predictable ladder:
- **Base:** 1–2 (default page and card layers)
- **Dropdown:** 15 (menus, popovers)
- **Modal:** 1000, 1030 (dialogs, full-page overlays; 1030 for the highest priority modal)

## 7. Do's and Don'ts

### Do
- **Use sharp corners throughout.** All buttons, cards, and interactive elements should have `border-radius: 0px` unless a pill-shape (9999px) is explicitly required by the design.
- **Maintain the navy–gold palette.** Primary (`#001F44`) and accent (`#FFAD00`) define the brand. Do not introduce new brand colours.
- **Leverage Montserrat at 400 and 700 weights.** Keep the typeface consistent; do not mix in other sans-serif families.
- **Honour the spacing system.** Use values from `{spacing.xxs}` through `{spacing.band}` for all padding, margins, and gaps. Do not invent in-between values.
- **Apply colour blocking over shadow layering.** Establish depth through background colour and position, not primarily through shadows.
- **Use uppercase, 0.6px letter-spacing for small labels and captions.** This distinguishes metadata from body copy without requiring a size change.
- **Provide clear hover and focus states for all interactive elements.** Buttons change background colour and shadow; links underline; form inputs gain a border colour matching the brand primary.
- **Stack responsive layouts vertically on mobile, horizontally on desktop.** Keep content single-column at 375px–768px; expand to multi-column layout at 1024px and above.

### Don't
- **Do not round corners.** The system design is rectilinear. Avoid `border-radius` values other than 0px or 9999px.
- **Do not add new colours to the palette.** The eight extracted colours define the complete vocabulary. Inventing greys, additional neutrals, or semantic colours breaks consistency.
- **Do not use serif or script typefaces.** Montserrat is the only font family in the system.
- **Do not exceed font weights of 300, 400, or 700.** These three weights are the entire system; 500, 600, 800+ do not exist in the extraction.
- **Do not invent spacing values outside the documented scale.** Use only the 10 spacing tokens; do not create intermediate values like 18px or 35px.
- **Do not layer multiple shadows.** The system uses single, discrete shadows at three elevation levels. Stacking shadows creates visual noise.
- **Do not hide interactive elements behind authentication without documenting them.** This design document covers only the public homepage; internal or protected pages are unknown.
- **Do not apply transparency excessively.** Only `0.5` (50%) opacity is in use. Avoid arbitrary transparency percentages like 30% or 75%.
- **Do not mix uppercase and sentence-case in labels.** Small captions and badges are uppercase with 0.6px tracking; body copy is sentence-case.

## 8. Responsive Behavior

### Breakpoints

| Breakpoint | Min Width | Content Column | Grid Columns | Nav Links Visible | Menu Toggle | Display Heading | Body Copy |
|---|---|---|---|---|---|---|---|
| **Mobile** | 375px | 1920px | 1 | 1 | Yes | 28px | 16px |
| **Tablet** | 768px | 1920px | 1 | 1 | Yes | 34px | 16px |
| **Desktop Small** | 1024px | 1920px | 3 | 10 | Yes | 37px | 16px |
| **Desktop Medium** | 1280px | 1920px | 3 | 10 | Yes | 40px | 16px |
| **Desktop Large** | 1440px | 1920px | 7 | 10 | Yes | 40px | 16px |

**Key Changes:**
- **375px → 768px:** No layout change; content remains single-column. Heading size grows modestly (28px → 34px). Menu toggle persists.
- **768px → 1024px:** Logical column count increases from 1 to 3; layout begins horizontal expansion. Heading reaches 37px. Navigation links visible; 10-link nav becomes available.
- **1024px → 1280px:** Column structure stabilizes at 3–7 columns. Heading size plateaus at 40px.
- **1280px+:** Grid expands to 7 logical columns; menu toggle remains for consistency but may hide on certain page types.

### Touch Targets
Interactive elements must meet a minimum 48px height and width for reliable touch interaction:
- **Buttons:** 47–50px height (measured); full-width on mobile, fixed width on desktop.
- **Input fields:** 40px+ height (form fields, searchable fields).
- **Navigation links:** 85px header height provides ample tap area.
- **Card clickable regions:** Minimum 378px width on desktop; full width minus gutters on mobile.

### Collapsing Strategy
- **Mobile (375px–768px):** Single-column stack. Cards, sections, and hero imagery scale to full width minus section padding (if any). Navigation collapses to hamburger menu or sticky header. Hero text and primary CTA remain large and prominent.
- **Tablet (768px–1024px):** Content begins horizontal grouping; cards may arrange in 2-column clusters, but primary content remains centered. Navigation starts to show inline links.
- **Desktop (1024px+):** Full multi-column layout. Cards, sections, and hero imagery leverage the 7-column grid or flexible containers. Navigation is fully horizontal with all links visible. Section padding is consistent; no edge-to-edge full-width sections except hero bands and footer.

## 9. Agent Prompt Guide

### Quick Color Reference
When implementing PISTA Digital components, refer to these primary semantic roles:

- **Primary CTA, Brand, Active State:** Primary (`{colors.primary}` — `#001F44`)
- **Secondary Accent, Hero Highlight:** Accent (`{colors.accent}` — `#FFAD00`)
- **Inline Links:** Link (`{colors.link}` — `#2066BC`)
- **Page Background, Canvas, Card Fills:** Canvas (`{colors.canvas}` — `#FFFFFF`)
- **Heading, Primary Body Text:** Ink (`{colors.ink}` — `#1D2127`)
- **Borders, Dividers, Secondary Text:** Hairline (`{colors.hairline}` — `#4E4F50`)
- **Decorative / Unassigned:** Neutral 1 (`#000000`), Neutral 2 (`#CED4DA`) — use sparingly for experimental or non-critical surfaces.

### Iteration Guide

1. **Start with typography.** All text is Montserrat; choose weight (400 or 700) and size from the hierarchy table. Never invent font sizes; all copy must map to an existing role (display, heading, body, button, caption).
2. **Apply the spacing scale.** Every pixel of padding, margin, or gap must use `{spacing.xxs}` through `{spacing.band}`. No in-between values.
3. **Use sharp corners (0px radius) as default.** Only apply 9999px (pill-shape) if a component is explicitly pill-shaped in the design.
4. **Color-block for hierarchy.** Establish visual depth through background colour, not shadow. Use `{colors.primary}` for dominant surfaces, `{colors.canvas}` for content, `{colors.hairline}` for subtle dividers.
5. **Constrain shadows to three levels:** Flat (none), micro-raised (`0px 2px 4px`), or elevated (`0px 8px 16px`). Do not invent intermediate shadow values.
6. **Design for touch on mobile.** Ensure interactive elements are ≥48px in height/width. Stack content vertically at <768px; expand to multi-column layout at ≥1024px.
7. **Provide all interaction states:** Hover, focus, active, disabled. Refer to the extracted interaction data for exact colors and effects (e.g., primary button hover becomes `#007FFF`).
8. **Test the responsive breakpoints.** Verify layouts at 375px, 768px, 1024px, 1280px, and 1440px. Heading sizes and column counts must change at the documented thresholds.
9. **Document deviations.** If a new page or component requires a colour, spacing value, or shadow not listed here, it represents a system gap; flag it rather than inventing a value.

## 10. Known Gaps

- **Semantic Status Ramp:** The site does not declare error, success, warning, or info colours in its markup. Form validation states (green focus on success, red on error) were extracted from stylesheet rules but are not part of a formal semantic palette; they are implementation details of the form library, not brand-defined roles. Do not assume a full status colour system exists.
- **Unassigned Neutral Colours:** Two colours (`{colors.neutral-1}` — `#000000` and `{colors.neutral-2}` — `#CED4DA`) appear in the extracted data but have no measured semantic role. They are decorative only; their usage context is unclear from the homepage alone. Do not rely on these colours for core interface elements.
- **Dark Mode / Theme Variants:** Only one theme (light) was measured. No dark mode, high-contrast mode, or alternative colour scheme was observed or extracted. If dark mode exists, it is not documented here.
- **Advanced Interaction States:** Drag-and-drop, multi-select, inline editing, and other complex interaction patterns were not present on the homepage and are not documented. The extracted interaction states are limited to hover, focus, active, and disabled on basic form controls and buttons.
- **Animated Transitions:** No CSS transition or animation rules were extracted. Timing, easing, and motion design are unknown; assume a static design unless animation is explicitly declared in a component specification.
- **Surfaces Behind Authentication:** Pages accessible only after sign-in were not visited. Internal dashboards, user settings, and protected views may use different component patterns or colours; they are outside the scope of this extraction.
- **Icon System:** Badge icons are FontAwesome (32px, white, transparent background), but a complete icon library spec is not documented. Icon sizing, stroke weight, fill rules, and naming conventions for non-badge contexts are unknown.
- **Print Styles:** No print media queries or print-specific styling was extracted. The design's behaviour when printed to PDF or paper is unknown.
- **Accessibility Specifics:** Focus ring styles, ARIA attributes, and screen-reader optimizations are not fully documented. The extraction captured some focus states (e.g., outline none on inputs) but not a comprehensive accessibility guide.
- **Gradient Directives:** Only one gradient was extracted: the hero band darkening (`linear-gradient(0deg, #001F44 0%, rgba(240, 240, 240, 0) 100%)`). Other gradients may exist on subpages or in different states; this is not a complete gradient library.