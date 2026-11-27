---
name: Civic Justice
colors:
  surface: '#f7f9fb'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#454556'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#757687'
  outline-variant: '#c5c5d9'
  surface-tint: '#3746ed'
  primary: '#0d1fd5'
  on-primary: '#ffffff'
  primary-container: '#3443eb'
  on-primary-container: '#d0d2ff'
  inverse-primary: '#bdc2ff'
  secondary: '#4c6075'
  on-secondary: '#ffffff'
  secondary-container: '#cce2fa'
  on-secondary-container: '#506579'
  tertiary: '#004e48'
  on-tertiary: '#ffffff'
  tertiary-container: '#006861'
  on-tertiary-container: '#8fe5da'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e0e0ff'
  primary-fixed-dim: '#bdc2ff'
  on-primary-fixed: '#000668'
  on-primary-fixed-variant: '#1223d7'
  secondary-fixed: '#cfe5fd'
  secondary-fixed-dim: '#b3c9e0'
  on-secondary-fixed: '#061d2f'
  on-secondary-fixed-variant: '#34495c'
  tertiary-fixed: '#9cf2e8'
  tertiary-fixed-dim: '#80d5cb'
  on-tertiary-fixed: '#00201d'
  on-tertiary-fixed-variant: '#00504a'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
typography:
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 26px
    letterSpacing: -0.01em
  title-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
  label-lg:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.02em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-lg: 1.5rem
  margin: 1.5rem
  margin-lg: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

## Brand & Style

This design system embodies an authoritative, approachable, and trustworthy civic-tech aesthetic tailored for Indian legal empowerment. The target audience spans everyday citizens seeking clarity on their legal rights, consumer protections, and government schemes, as well as legal-aid seekers navigating formal documentation. The interface must evoke calm confidence, institutional credibility, and effortless clarity—demystifying complex legal processes without feeling cold or intimidating.

The visual language blends **Corporate / Modern** structure with **Minimalism**:
- **High-clarity surfaces:** Pure white canvases (`#FFFFFF`) paired with subtle cool-slate surfaces (`#F8FAFC`) keep dense legal text, case histories, and AI chat responses effortless to scan.
- **Institutional anchor:** A persistent deep navy sidebar (`#0F2537`) provides unwavering navigational grounding, contrasting cleanly against the bright workspace.
- **Purposeful accents:** Vibrant electric blue (`#3443EB`) signals primary actions, active states, and AI-assisted guidance, while crisp 1px borders (`#E2E8F0`) and restrained elevation maintain structural precision.

## Colors

The palette balances institutional authority with modern digital clarity in a **light** default color mode:

- **Primary (`#3443EB` / `#1D4ED8`):** Electric blue drives all primary calls-to-action (such as `+ New Complaint`, send buttons, and active navigation pills), interactive focus rings, and AI assistant accents. `#1D4ED8` serves as the hover and pressed state.
- **Secondary (`#0F2537` / `#132A46`):** Deep navy blue anchors the persistent left navigation rail, primary page headings, and high-emphasis typography, establishing immediate legal-tech credibility.
- **Neutral (`#FFFFFF` / `#F8FAFC` / `#E2E8F0`):** Pure white (`#FFFFFF`) forms the primary workspace canvas and card surfaces, while `#F8FAFC` provides subtle tonal separation for secondary containers, upload zones, and table/list headers. Crisp `#E2E8F0` 1px borders define structural boundaries.
- **Semantic & Status Accents:** Soft, accessible status tints communicate document and case states—emerald (`#ECFDF5` / `#059669`) for filed or secure items, soft indigo/blue (`#EFF6FF` / `#2563EB`) for saved items and user chat bubbles, muted violet (`#F5F3FF` / `#7C3AED`) for drafts, and restrained crimson (`#DC2626`) reserved strictly for destructive actions and logout controls.

## Typography

The typographic hierarchy pairs **Plus Jakarta Sans** for headings with **Inter** for body copy, UI controls, and metadata:

- **Headings (`Plus Jakarta Sans`):** Used for hero prompts ("How can SATYA help you?"), page titles ("Case History", "Document Library"), and section headers. Tight negative letter-spacing (`-0.015em` to `-0.02em`) gives large navy headings a modern, editorial authority.
- **Body & Controls (`Inter`):** Chosen for its exceptional legibility at small sizes, tabular numerals for dates and case IDs, and neutral clarity across long-form legal explanations, AI chat responses, and statutory citations.
- **Responsive Scaling:** On mobile viewports, `headline-lg` steps down to `headline-lg-mobile` (`24px`), while `body-md` (`14px`) remains the workhorse for readable legal content and form inputs.

## Layout & Spacing

This design system uses a **fluid grid** paired with a fixed-width persistent left navigation sidebar (`240px` on desktop) to create a predictable, application-grade workspace.

- **Grid & Rhythm:** Content areas operate on a 12-column fluid grid with `1rem` (`16px`) gutters on compact viewports and `1.5rem` (`24px`) gutters on desktop. Outer canvas margins are `1.5rem` (`24px`) on tablet/mobile and `2rem` (`32px`) on desktop.
- **Breakpoints & Adaptation:**
  - **Desktop (`>= 1024px`):** Persistent left navy sidebar, full 12-column workspace, multi-column category grids (4-up), and side-by-side profile/account cards.
  - **Tablet (`768px - 1023px`):** Collapsible or compact rail sidebar; 4-column category grids reflow to 2x2.
  - **Mobile (`< 768px`):** Sidebar collapses into a top header bar with a slide-over drawer. Cards, list rows, and action buttons stack vertically with `1rem` (`16px`) gaps.
- **Spacing Scale:** Built on a strict `4px` (`0.25rem`) base unit. Use `space-xs` (`4px`) and `space-sm` (`8px`) for tight icon-to-label pairings and chip padding; `space-md` (`16px`) for card padding and list item gaps; `space-lg` (`24px`) and `space-xl` (`32px`) for section separation.

## Elevation & Depth

Visual hierarchy relies primarily on **low-contrast outlines** and **tonal layers**, supplemented by **ambient shadows** only for floating or interactive focal points:

- **Crisp 1px Borders:** Cards, list containers, input fields, and secondary buttons use a `1px solid #E2E8F0` border on `#FFFFFF` or `#F8FAFC` surfaces to define structure without visual clutter.
- **Tonal Layering:** Subtle background shifts between `#FFFFFF` (primary cards) and `#F8FAFC` (drag-and-drop upload zones, user profile sub-cards, and hover states) establish hierarchy cleanly.
- **Ambient Shadows:** Reserved for the primary hero search/prompt bar, active dropdowns, and elevated category cards on hover. Shadows use a diffused, low-opacity navy tint (`0 4px 16px -2px rgba(15, 37, 55, 0.06)`) to feel crisp and grounded rather than heavy.

## Shapes

The shape language uses a **Rounded (`0.5rem` / `8px`)** baseline, striking a balance between approachable consumer software and structured legal professionalism:

- **Standard (`0.5rem` / `8px`):** Applied to primary/secondary buttons, input fields, sidebar navigation items, and standard list rows.
- **Large (`1rem` / `16px`):** Applied to content cards, chat message bubbles, and the drag-and-drop document upload zone.
- **Pill (`9999px`):** Reserved for quick-action prompt chips ("Can I file a case?", "Know my rights"), filter tabs ("All", "Acts", "Rules"), status badges ("Saved", "Draft", "Filed", "Secure"), and the main AI prompt input bar.

## Components

- **Persistent Sidebar Navigation:** Deep navy (`#0F2537`) background with white/muted-slate (`#94A3B8`) icons and labels. The active route uses an electric blue (`#3443EB`) pill/rounded container with crisp white text. Logout sits anchored at the bottom in restrained crimson (`#EF4444` / `#DC2626`).
- **Buttons:**
  - *Primary:* Solid electric blue (`#3443EB`), white `label-lg` text, `0.5rem` radius, `#1D4ED8` hover state.
  - *Secondary / Outline:* White (`#FFFFFF`) background, `1px solid #E2E8F0` border, navy (`#0F2537`) or electric blue (`#3443EB`) text, `#F8FAFC` hover.
  - *Destructive / Logout:* Soft red-tinted outline or ghost button (`#FEF2F2` hover, `#DC2626` text).
- **Chips & Filter Pills:** Pill-shaped (`9999px`) with `1px solid #E2E8F0` border on `#FFFFFF` for unselected states; solid navy (`#0F2537`) or electric blue (`#3443EB`) fill with white text when active. Status badges use soft tinted backgrounds (`#ECFDF5`, `#EFF6FF`, `#F5F3FF`) with matching dark semantic text.
- **Cards & List Rows:** White (`#FFFFFF`) surface, `1px solid #E2E8F0` border, `1rem` (`16px`) padding, and `0.75rem`–`1rem` corner radius. Category cards center-align a `32px`–`40px` duotone/line icon above a `title-md` label.
- **Input Fields & AI Prompt Bar:** Standard inputs use `1px solid #E2E8F0`, `0.5rem` radius, and a `#3443EB` focus ring. The central AI prompt bar uses a pill container with subtle ambient shadow, left-aligned placeholder text, and right-aligned attachment, microphone, and circular electric blue send buttons.
- **Checkboxes & Radio Buttons:** `1px solid #CBD5E1` borders with `0.25rem` radius (checkboxes) or circular (radios), filling with `#3443EB` and a crisp white checkmark/dot when selected.
- **Chat Bubbles (Legal Assistant):** User messages align right on a soft blue-slate tint (`#EFF6FF`) with navy text. Assistant responses align left on a crisp white card with a subtle blue-tinted border (`#BFDBFE`), paired with a circular electric blue scale-of-justice avatar, structured numbered lists, and a pill-shaped statutory source citation tag.