# UX Audit Checklist

Baseline: WCAG 2.1 AA compliance for all accessibility items.

## 1. Navigation & Flow

- Can users find every feature from the sidebar/nav without guessing?
- Are there dead-end pages with no back button or next action?
- Do breadcrumbs exist where depth > 2 levels?
- Are active nav items visually distinct from inactive?
- Does the URL reflect where the user is (deep-linkable)?
- After completing an action, does the user land somewhere useful?
- Are related features grouped logically in navigation?

## 2. Task Completion Friction

- Can users complete the primary task on each page without unnecessary steps?
- Is data entry repeated across steps that could share context?
- Are multi-step flows linear or does premature branching confuse?
- Is the next action always obvious (clear CTA)?
- Do flows require users to remember info from prior screens?
- Can users save progress in long forms or do they lose work on navigate-away?
- Are confirmation steps proportional to the action's risk?

## 3. Error States & Edge Cases

- Does every form show inline validation errors with specific messages?
- Do API failures show user-friendly errors (not raw status codes or stack traces)?
- Is there a meaningful empty state for every list/table (not just blank space)?
- Do empty states guide the user toward the next action?
- Are 404 pages helpful (suggest navigation, not just "not found")?
- Do timeout errors offer retry options?
- Are error toasts distinguishable from success toasts?

## 4. Feedback & System Status

- Is there a loading indicator for every async operation?
- Do buttons show loading state when clicked (disabled + spinner)?
- Are save operations confirmed visually (toast, checkmark, status change)?
- Are disabled buttons/controls explained (tooltip or adjacent text)?
- Do background jobs show progress (upload percentage, sync status)?
- Is there visual feedback for every user interaction (hover, focus, active)?
- Do status badges use consistent color coding across the app?

## 5. Consistency & Patterns

- Do similar features use the same UI pattern (tables, cards, dialogs)?
- Are action buttons in consistent positions across pages (top-right, footer)?
- Is terminology consistent (don't mix "delete/remove", "create/add", "save/submit")?
- Do toggles, switches, and selectors work the same way everywhere?
- Are date/time formats consistent across the app?
- Do confirmation dialogs follow the same pattern (AlertDialog vs custom)?
- Is the color system consistent (green=success, red=danger, yellow=warning)?

## 6. Forms & Input UX

- Are required fields marked clearly (asterisk, "required" label)?
- Does validation happen at the right time (not just on submit)?
- Are format requirements visible before the user types (placeholder, hint text)?
- Do password/secret fields have show/hide toggles?
- Are dropdowns searchable when they have > 7 options?
- Do forms preserve input on validation failure (not clear fields)?
- Are multi-select vs single-select controls visually distinct?
- Is tab order logical (left-to-right, top-to-bottom)?

## 7. Content Clarity & Information Scent

- Are labels specific (not "Settings" — settings for what)?
- Is jargon explained or avoided (what is "BYO Database" to a new user)?
- Do CTAs describe their outcome ("Create API Key" not "Submit")?
- Can users predict where a link/button will take them?
- Are headings descriptive enough to scan the page without reading body text?
- Is related information grouped with clear visual boundaries?
- Are numbers/stats contextualized (is "1,000" good or bad?)?

## 8. Accessibility (WCAG 2.1 AA)

### Keyboard & Focus
- Can every interactive element be reached via keyboard (Tab)?
- Is focus visible on all focusable elements (outline, ring)?
- Is focus trapped correctly inside modals/dialogs (cannot Tab behind them)?
- Is tab order logical and follows visual layout?
- Is there a skip-to-content link for keyboard users?

### Screen Readers & Semantics
- Do screen readers announce element purpose (aria-label on icon buttons)?
- Are status changes announced to screen readers (aria-live regions)?
- Do images have meaningful alt text (not "image" or empty)?
- Are form errors associated with their fields (aria-describedby)?
- Are heading levels correct and sequential (no skipping H1 → H3)?
- Are landmark regions used appropriately (main, nav, aside, footer)?
- Do `role` attributes match element behavior (role="button" on clickable divs)?

### Visual & Motor
- Is color contrast sufficient (4.5:1 for normal text, 3:1 for large text)?
- Are tap/click targets at least 44x44px?
- Does the app respect `prefers-reduced-motion`?
- Is information conveyed by means other than color alone (icons, text, patterns)?
- Can the page be zoomed to 200% without loss of content or functionality?

## 9. Responsive & Layout

- Does the layout work at common breakpoints (375px, 768px, 1024px, 1440px)?
- Do tables have horizontal scroll or responsive alternatives on mobile?
- Are sticky headers/footers covering interactive content?
- Do modals/dialogs work on small screens (not clipped, scrollable)?
- Are touch targets spaced enough to avoid accidental taps?
- Does the sidebar collapse properly on mobile?
- Are images/icons sized appropriately (not blurry, not oversized)?

## 10. Trust, Risk & Support Triggers

- Do destructive actions have confirmation dialogs with clear consequences?
- Are irreversible actions visually distinct (red button, warning icon)?
- Is it clear what "test mode" vs "live/production mode" means everywhere?
- Do permission-limited features explain WHY they're disabled (not just gray)?
- Are pricing/billing changes previewed before confirmation?
- Does the app explain what happens to data on delete/cancel/downgrade?
- Are security-sensitive pages (API keys, billing) visually differentiated?

## 11. Onboarding & Discoverability

- Can a new user understand what the product does from the first screen?
- Is there a clear "getting started" path after signup?
- Are new/advanced features discoverable (tooltips, "new" badges)?
- Does the app guide users through first-time setup (provider config, etc.)?
- Are help links or documentation accessible from relevant pages?

## 12. Visual Hierarchy & Scanning

- Is the most important element on each page immediately obvious?
- Do headings create a clear content hierarchy (H1 > H2 > H3)?
- Are primary actions visually dominant over secondary actions?
- Is whitespace used to group related elements?
- Does anything compete for attention unnecessarily (too many badges, alerts)?

## 13. Recovery & Reversibility

- Can users undo recent actions (undelete, restore)?
- Can users retry failed operations without re-entering data?
- Can users safely navigate back without losing progress?
- Are "cancel" buttons safe (no data loss without warning)?
- Do session timeouts preserve unsaved work or warn before expiry?

## 14. Performance & Perceived Speed

- Does the largest visible element load within 2.5 seconds (LCP)?
- Are there visible layout shifts after page load (CLS > 0.1)?
- Do pages use skeleton loaders instead of blank space or full-page spinners?
- Is optimistic UI used where appropriate (instant feedback before server confirms)?
- Are images lazy-loaded below the fold?
- Do long lists use virtualization or pagination (not rendering 1000+ DOM nodes)?
- Are heavy operations (file uploads, exports) non-blocking with progress indicators?
- Does the app feel responsive to clicks/taps (< 100ms visual feedback)?

## 15. Data & Table UX

- Is pagination or infinite scroll implemented for large datasets?
- Are sort and filter controls discoverable (not hidden behind menus)?
- Can users perform bulk actions on multiple rows (select all, batch delete)?
- Are column headers clear and is the current sort direction visible?
- Can users resize or reorder columns (for data-heavy apps)?
- Is there an export option for table data (CSV, Excel)?
- Do tables show meaningful empty states (not just an empty grid)?
- Are long cell values truncated with tooltips or expandable rows?
- Does the table preserve scroll position and selections on data refresh?

## 16. Search UX

- Is the search input discoverable and accessible from every page (or key pages)?
- Does search provide autocomplete or suggestions?
- Are search results relevant and sorted sensibly (relevance, recency)?
- Does empty search results state help users refine their query?
- Is the search scope clear (searching all content vs current section)?
- Are recent searches or popular queries shown for discoverability?
- Can users clear the search and return to the previous state?
- Does search handle typos or near-matches gracefully?

## 17. Dark Mode & Theme Consistency

*Skip this category if the app does not support theming or dark mode.*

- Do all pages render correctly in both light and dark modes?
- Are custom colors (status badges, charts, highlights) visible in both themes?
- Are images and icons adapted for dark backgrounds (no white halos, transparent PNGs)?
- Does the theme toggle persist across sessions?
- Are focus rings and outlines visible in both themes?
- Do third-party embeds (maps, widgets, iframes) respect the current theme?
- Is contrast ratio maintained in both themes (re-check WCAG 4.5:1)?

## 18. Internationalization & Localization

*Skip this category if the app does not support multiple languages/locales.*

- Are all user-facing strings externalized (no hardcoded text in components)?
- Do translated strings fit their containers (German/Finnish text is ~30% longer)?
- Does the layout support RTL languages if relevant (Arabic, Hebrew)?
- Are dates, times, numbers, and currencies formatted per locale?
- Are pluralization rules handled correctly (not just appending "s")?
- Do icons and images avoid culture-specific assumptions (mailbox styles, hand gestures)?
- Is the language/locale selector accessible and persistent?
