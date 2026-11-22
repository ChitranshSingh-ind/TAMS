# TAMS UI/Style Design Audit

Audit date: 2026-11-22

## Executive Summary

TAMS already has a recognizable visual identity: navy structure, warm gold
accents, cream surfaces, and consistent table styling. The design is
usable and coherent across the dashboard, students, attendance, fees,
analysis, and messaging areas.

The main opportunities are to improve visual hierarchy, reduce redundant
page-specific styling, replace emoji-only or text-only controls with
consistent iconography, improve keyboard and assistive-technology support,
strengthen contrast and disabled states, and make dense screens more
comfortable at common desktop sizes.

An offscreen rendering pass at 1280x800 showed no obvious clipping in the
representative dashboard, students, attendance, fees, analysis, and
messaging screens.

## Strengths

- The navy, gold, cream, and white palette is distinctive and consistent.
- Shared table styling provides predictable headers, selection, scrolling,
  and alternate rows.
- Every primary page has a clear title and short explanatory subtitle.
- Global focus rings and hover states are present for many core controls.
- Table overflow uses horizontal scrolling and hover tooltips.
- Dashboard cards and summary panels provide a compact overview.
- Dialog forms use structured labels, required-field markers, and clear
  primary and secondary button patterns.

## Priority 1: Visual hierarchy and density

### 1. Dashboard has too much empty card and panel space

**Evidence:** `app/ui/mixins/dashboard_mixin.py:49-100`,
`app/ui/mixins/dashboard_mixin.py:103-166`

At 1280px, the four KPI cards are very tall while the most important value
occupies only a small section of each card. The lower panels are also broad
and sparse with no data. This leaves the dashboard visually quiet but wastes
space that could improve scanability.

Recommended improvements:

- Reduce KPI card height and place title, value, and short description on a
  tighter baseline.
- Add subtle colored indicators or icons that identify each KPI category.
- Use a more compact lower-section height or let it fill remaining vertical
  space only when content is present.
- Replace blank lower-card content with structured empty states, next actions,
  or a short explanation.

### 2. Page headers compete with too many actions

**Evidence:** `app/ui/mixins/students_mixin.py:49-100`,
`app/ui/mixins/fees_mixin.py:70-112`,
`app/ui/mixins/analysis_mixin.py:87-125`

Students has three nearly equally emphasized header actions. Fees has three
header actions plus KPI cards and filters. Analysis has batch and period
filters, an export menu, refresh, tab navigation, four KPI cards, tables, and
other dense controls.

Recommended improvements:

- Establish one primary action per page.
- Move secondary actions into overflow menus or a consistent toolbar.
- Use label + icon patterns consistently rather than emoji in some places and
  text-only controls in others.
- Keep filters in a separate, visually lighter toolbar from page actions.

### 3. Dense pages need a clearer secondary hierarchy

**Evidence:** `app/ui/mixins/analysis_mixin.py:253-279`,
`app/ui/mixins/analysis_mixin.py:374-394`,
`app/ui/mixins/fees_mixin.py:147-158`

Several KPI cards use similarly styled borders, text sizes, and values.
Section titles and card titles also vary significantly between modules.

Recommended improvements:

- Define typography roles for page title, section title, card label, metric,
  body text, caption, and table header.
- Use one card component or shared helper across all pages.
- Reserve color for status or semantic meaning rather than decoration.
- Use stronger separation between data regions and controls.

## Priority 2: Consistency

### 1. Inline styles duplicate the design system

**Evidence:** `app/ui/theme.py:5-20`, `app/ui/mixins/fees_mixin.py:147-158`,
`app/ui/mixins/students_mixin.py:101-145`,
`app/ui/mixins/analysis_mixin.py:87-134`

The repository defines shared palette constants, but many widgets still use
complete inline stylesheets and literal hex values. This makes spacing,
radius, typography, and states differ between screens.

Recommended improvements:

- Create shared helper functions or classes for:
  - primary, secondary, danger, and ghost buttons;
  - page headers;
  - toolbar/filter layouts;
  - KPI cards;
  - section cards;
  - empty states;
  - status badges.
- Centralize typography sizes and spacing tokens.
- Generate chevron and app icons through a consistent asset system.
- Add a dark-mode-neutral semantic palette even if dark mode is not initially
  implemented.

### 2. Iconography is inconsistent

**Evidence:** `app/ui/main_window.py:124`, sidebar labels in
`app/ui/main_window.py:188-221`, student actions in
`app/ui/mixins/students_mixin.py:64-98`

The interface mixes a Unicode gear, emoji menu labels, text-only buttons,
and native Qt icons. Emoji rendering can vary across Windows versions and
font installations.

Recommended improvements:

- Replace Unicode/emoji controls with a consistent SVG icon set.
- Retain text labels for primary actions and module names.
- Use icons to reinforce meaning, not as the only label.
- Define standard icon sizes for 16px, 20px, and 24px contexts.
- Use vector assets for the app logo and all navigation icons.

### 3. Control heights and radii vary

The code uses a range of heights and radii in separate widgets, including
36px, 38px, 40px, and 42px controls, 6px to 10px radii, and inconsistent
padding.

Recommended improvements:

- Define compact 36px and standard 40px control sizes.
- Use 6px for inputs and cards, 8px for buttons, and 10px for major panels.
- Align all controls in a toolbar to the same height.
- Use a consistent 12px or 16px horizontal page gutter.

## Priority 3: States and feedback

### 1. Empty states are mostly unstructured text

**Evidence:** dashboard in
`app/ui/mixins/dashboard_mixin.py:220-254`, fees in
`app/ui/mixins/fees_mixin.py:292-294`,
`app/ui/mixins/teaching_mixin.py:320-359`

Some empty states are short labels in dashed frames or bare sentences. They
do not consistently explain why there is no data or suggest a next action.

Recommended improvements:

- Add one shared empty-state component with icon, title, explanation, and
  optional action.
- Distinguish "no data yet," "no result for filters," and "setup required."
- Preserve useful filter context in search and table empty states.
- Avoid error-like red or amber styling unless a real warning exists.

### 2. Loading, busy, and success feedback is uneven

Several worker operations show result dialogs or status text, but the app
does not consistently provide a visible busy state or disable repeated
actions.

Recommended improvements:

- Add a shared busy overlay or progress indicator for long operations.
- Disable repeated submission and export actions while workers are running.
- Use toasts or concise status banners for successful operations.
- Keep destructive confirmation dialogs explicit and consistent.
- Add retry actions beside failed operations where recovery is possible.

### 3. Disabled controls need stronger visual and accessibility treatment

**Evidence:** `app/ui/main_window.py:662-665`,
`app/ui/main_window.py:1262-1267`

The disabled palette is available, but action states should include:

- lower contrast without becoming unreadable;
- a stable position and width;
- a clear tooltip or nearby explanation;
- no misleading hover behavior.

Recommended improvements:

- Avoid the pale gray-on-gray combination for critical status labels.
- Explain disabled buttons, especially attendance, save, and restore actions.
- Add tooltips for disabled controls rather than relying on surrounding text.

## Priority 4: Accessibility

### 1. Keyboard and screen-reader metadata is incomplete

**Evidence:** settings button and sidebar construction in
`app/ui/main_window.py:124-126`, `app/ui/main_window.py:201-220`

The audit found no consistent use of accessible names, descriptions,
tooltips, or accessible widgets across the interface.

Recommended improvements:

- Set accessible names and descriptions for icon-only controls.
- Provide accessible labels for every custom chart and status badge.
- Preserve visible focus state for all interactive widgets.
- Test full keyboard navigation through page, table, dialog, and menu flows.
- Use logical tab order and avoid controls that only respond to mouse events.

### 2. Dashboard cards are mouse-only

**Evidence:** `app/ui/mixins/dashboard_mixin.py:68-99`

Dashboard cards navigate on `mousePressEvent`, but do not expose a standard
keyboard/button interaction.

Recommended improvements:

- Use `QPushButton` or an accessible custom card button.
- Give cards a visible focus indicator.
- Expose navigation purpose in the accessible name.
- Avoid dynamically replacing mouse events with lambdas.

### 3. Color should not be the sole status indicator

Status tables and fee, attendance, expense, and message views use both text
and color, which is positive. Other controls may rely on border, fill, or
color alone.

Recommended improvements:

- Pair status colors with text or symbols.
- Verify text contrast for muted text and gold accents.
- Provide high-contrast focus colors that remain visible on cream surfaces.
- Test a full grayscale rendering to ensure layout is still understandable.

## Priority 5: Layout and responsiveness

### 1. The app is fixed to a desktop-first layout

**Evidence:** `app/ui/main_window.py:76-82`,
`app/ui/main_window.py:181-183`

The initial 1280x800 size is reasonable, but the sidebar is fixed at 210px
and several pages use fixed-height controls and large dialog widths.

Recommended improvements:

- Define minimum supported window sizes and document them.
- Test 1024x768 and 1366x768 explicitly.
- Allow the sidebar to collapse or shrink on narrow windows.
- Prefer proportional or bounded table widths to fixed absolute widths.
- Use a scrollable page wrapper for very short windows.

### 2. Toolbar wrapping is not guaranteed

Many HBox layouts add fixed-width filters and actions in sequence. If the
window shrinks or the app name grows, actions can overlap or disappear.

Recommended improvements:

- Use a `QGridLayout` or a two-row toolbar at constrained widths.
- Group related filters and provide a separate overflow menu.
- Allow the search field to shrink and priority actions to remain visible.
- Test localized or longer labels as layout stress cases.

### 3. Dialog sizing varies widely

Dialogs use combinations of fixed minimum widths, fixed heights, fixed
maximum heights, and manually chosen resize values.

Recommended improvements:

- Use minimum, default, and maximum sizes instead of absolute fixed sizes.
- Add scrolling to tall form dialogs.
- Use consistent 500px to 650px widths for common edit dialogs.
- Keep confirmation dialogs compact and isolated from complex forms.

## Priority 6: Tables and data presentation

**Evidence:** `app/ui/table_utils.py:14-88`,
`app/ui/table_utils.py:146-210`,
`app/ui/main_window.py:606-646`

Table utilities are a strong feature, especially the bounded/flexible sizing
and hover tooltips.

Recommended improvements:

- Keep numeric fields right-aligned or clearly tabular; current table alignment
  may need to be reviewed per module.
- Add sorting indicators and consistent sort behavior.
- Show clearer status chips instead of plain colored text where appropriate.
- Preserve selected rows and scroll position after refresh consistently.
- Add sticky first columns for wide operational tables if needed.
- Add a compact density option for power users.
- Ensure action columns remain last and visually separated.
- Use visible "No rows found" states with filter reset guidance.

## Priority 7: Typography and brand expression

**Evidence:** `app/ui/theme.py:12-20`,
`app/ui/main_window.py:797-806`,
`app/ui/chart_widgets.py:61-75`

The design uses a large number of literal font sizes and weight combinations.
The Inter font is requested in stylesheets, but desktop systems may not have
it installed.

Recommended improvements:

- Bundle one licensed Unicode-compatible desktop font or consistently use
  native system fonts.
- Create a clear type scale instead of module-specific 22px, 26px, 28px, and
  other values.
- Avoid using bold and all-caps excessively in table headers and labels.
- Limit letter spacing to uppercase metadata and badges.
- Improve Indian currency formatting and alignment without changing the data.

## Priority 8: Charts and data visualization

**Evidence:** `app/ui/chart_widgets.py:12-28`,
`app/ui/chart_widgets.py:179-220`

The custom charts are dependency-free and polished, but some details should
be improved for readability.

Recommended improvements:

- Add visible axes or a legend only where it improves interpretation.
- Display a concise explanation and unit with every chart.
- Avoid long elided labels without a tooltip or detail table.
- Add keyboard-accessible summaries for chart results.
- Preserve chart aspect ratio as the container changes.
- Expose no-data and partial-data states separately.
- Use a tested color-safe status palette for all distributions.

## Priority 9: Form and dialog UX

**Evidence:** `app/ui/add_student_dialog.py:27-46`,
`app/ui/add_student_dialog.py:63-123`,
`app/ui/main_window.py:1176-1286`

The form structure is good, but several common patterns can be more
predictable.

Recommended improvements:

- Use required markers consistently and add a legend if the form is dense.
- Do not show `specialValueText("Date of birth")` with a 1900 minimum date
  unless it is visually and behaviorally clear.
- Place save and cancel actions in a stable footer.
- Add inline validation instead of only modal error messages.
- Preserve entered values after validation failures.
- Use clear destructive confirmation copy rather than generic confirmation
  text.
- Use same-width primary actions in dialog button rows.

## Priority 10: High-value visual upgrades

The current interface would benefit most from:

1. A shared component library for cards, buttons, page headers, empty states,
   and badges.
2. One primary action and one clear visual hierarchy per page.
3. A complete SVG icon set to replace emoji and mixed text icons.
4. A responsive sidebar and toolbar behavior below 1280px.
5. Stronger empty states with useful next steps.
6. Improved keyboard navigation and accessible names.
7. Separate loading, success, warning, and error patterns.
8. A documented 8px spacing scale and semantic type scale.
9. Better status and chart palettes validated for contrast.
10. Consolidation of inline stylesheets into reusable tokens.

## Suggested Component Standard

### Recommended spacing

- 4px: compact internal spacing
- 8px: control spacing
- 12px: compact component padding
- 16px: standard component padding
- 24px: page gutter
- 32px: major page or section separation

### Recommended control heights

- Compact toolbar: 36px
- Standard input/button: 40px
- Large primary action: 44px
- Table row: 48px to 56px

### Recommended typography

- App title: 20px to 22px
- Page title: 24px to 26px
- Section title: 16px
- Card metric: 24px to 28px
- Body: 13px
- Caption: 11px to 12px

### Recommended semantic colors

- Primary: navy
- Accent: gold
- Surface: cream or white
- Text: dark neutral
- Muted text: medium warm neutral
- Success: green with text label
- Warning: amber with text label
- Danger: red with text label
- Information: blue with text label

## Recommended Validation Pass

- Capture 1024x768, 1280x800, 1366x768, 1920x1080, and 4K layouts.
- Test every module with empty data and a realistic populated dataset.
- Test 200% Windows display scaling.
- Test 150% and 200% Qt text scaling.
- Test keyboard-only navigation, including dialogs and tables.
- Test all icon-only and emoji-only controls with an accessibility object
  inspection tool.
- Test long student names, batch names, message bodies, addresses, and notes.
- Test text with deformed or missing Inter/font resources.
- Compare all module screenshots against shared spacing and typography roles.
- Verify every status with text plus icon or explicit label.

## Deep Review: Remaining Modules and Dialogs

### Priority 1: Complex workflows need clearer action hierarchy

**Evidence:** `app/ui/mixins/results_mixin.py:67-155`,
`app/ui/mixins/teaching_mixin.py:78-126`,
`app/ui/mixins/expenses_mixin.py:78-138`,
`app/ui/bulk_student_dialog.py:352-391`

Results, teaching, and expenses place multiple equally sized actions in the
top header. The bulk student dialog combines a large selection table,
filters, a tabbed transfer/status action card, and a footer in one 840x700
window.

Recommended improvements:

- Keep one navy primary action and visually subordinate neutral actions.
- Separate destructive actions with red text and a confirmation dialog.
- Split bulk student promotion and lifecycle status updates into separate
  confirmation steps if they can have different consequences.
- Reduce footer density and keep Apply/Save disabled until a selection and
  valid destination are present.
- Add a concise selected-count summary near bulk actions.

### Priority 2: Attendance has ambiguous compact controls

**Evidence:** `app/ui/mixins/attendance_mixin.py:50-143`,
`app/ui/mixins/attendance_mixin.py:203-239`

The attendance table uses only "A" and "P" as headers, with a four-column
table and no selection behavior. The warning, summary, bulk controls, and
save controls compete for attention.

Recommended improvements:

- Replace "A" and "P" headers with "Absent" and "Present" or a legend with
  accessible abbreviations.
- Use labeled segmented controls or radio-style cells instead of isolated
  narrow columns.
- Place attendance summary beside the batch/date toolbar.
- Keep the save action disabled and explain it when no batch or changes exist.
- Add a clear unsaved-change indicator and avoid losing edits on date/batch
  changes.
- Add a keyboard-accessible shortcut or row-level status control.

### Priority 3: Results header actions are too numerous

**Evidence:** `app/ui/mixins/results_mixin.py:67-155`,
`app/ui/mixins/results_mixin.py:206-220`

Create Test is primary, while Check Results, Edit Results, and Delete Test
remain in the header. The test table and detail dialogs also have distinct
interaction patterns.

Recommended improvements:

- Move Edit and Delete into a selected-test context menu or table action
  column.
- Keep one Check Results or View Results action as the primary post-selection
  action.
- Add visible selection state and a selected-test summary beside the toolbar.
- Include test status, entered marks count, and completion percentage in the
  test list if those values are available.

### Priority 4: Teaching tabs expose too much at once

**Evidence:** `app/ui/mixins/teaching_mixin.py:227-254`,
`app/ui/mixins/teaching_mixin.py:261-388`

Teaching combines three creation actions, five KPI cards, filters, and four
tabs with independent tables. The 1280px viewport can become visually busy
even though each tab is logically distinct.

Recommended improvements:

- Move "Record Class" and "Add Homework" into contextual action menus or the
  relevant tab.
- Keep only "Plan Lesson" as the primary header action.
- Consider compact summary cards or a collapsible overview.
- Rename tabs to match their actual task: Lessons, Class History, Homework,
  and Progress.
- Add a small count to each tab label.

### Priority 5: Expenses and fees tables are data-heavy

**Evidence:** `app/ui/mixins/expenses_mixin.py:257-285`,
`app/ui/mixins/fees_mixin.py:180-236`,
`app/ui/mixins/expenses_mixin.py:339-416`

The expenses table has ten columns, including several currency values and
actions. The fee table similarly has many operational fields. Currency values
need consistent right alignment and a more compact visual treatment.

Recommended improvements:

- Right-align amount and balance columns.
- Use status chips instead of plain status text where appropriate.
- Place reverse, history, and receipt actions behind an overflow menu.
- Add row actions that appear on hover/focus rather than permanently consuming
  wide columns.
- Freeze key description and student-name columns for horizontal scrolling.
- Provide visible filtered-row and total-amount summaries.

### Priority 6: Form dialogs are inconsistent

**Evidence:** `app/ui/fee_dialogs.py:58-123`,
`app/ui/expense_dialogs.py:54-140`,
`app/ui/teaching_dialogs.py:126-220`,
`app/ui/add_student_dialog.py:27-123`

Several dialogs use fixed heights, fixed control heights, manual footers,
different title sizes, and local validation dialogs. Required markers and
optional labels are not consistently defined.

Recommended improvements:

- Create shared form spacing and title patterns.
- Use 36px compact controls, 40px standard actions, and 44px primary actions.
- Put save/cancel in a fixed footer and keep it stable while content scrolls.
- Replace modal validation-only messages with inline labels and first-error
  focus.
- Preserve field values and highlight invalid fields after failed submission.
- Add field-level helper text for due dates, batch selection, and payment
  totals.

### Priority 7: Monthly fee preview lacks a stronger decision state

**Evidence:** `app/ui/fee_dialogs.py:142-220`,
`app/ui/fee_dialogs.py:220-300`

The monthly generation dialog presents preview and summary behavior, but
the primary action does not clearly communicate its scope, exact count, or
potential duplicates.

Recommended improvements:

- Show batch, month, due date, eligible count, skipped count, and estimated
  total before generation.
- Disable generation until preview completes.
- Add duplicate-preview and existing-fee warnings.
- Display successful creation progress and a final summary.
- Avoid emoji in preview buttons; use clear action labels.

### Priority 8: Payment and reversal dialogs need stronger hierarchy

**Evidence:** `app/ui/expense_dialogs.py:125-180`,
`app/ui/expense_dialogs.py:630-680`,
`app/ui/fee_dialogs.py:870-950`

Payment details, fees, and reversal confirmation use form-heavy layouts.
Destructive and non-destructive actions do not always have a clear visual
separation.

Recommended improvements:

- Use a success or neutral color for payment confirmation.
- Use red only for reversal, delete, and failed states.
- Explain the financial effect of reversal and require a reason.
- Show remaining balance and result status before final confirmation.
- Use a dedicated high-risk confirmation layout for irreversible operations.

### Priority 9: Printing dialogs need richer responsive behavior

**Evidence:** `app/ui/print_dialogs.py:262-335`,
`app/ui/print_dialogs.py:446-526`,
`app/ui/print_dialogs.py:658-766`

The receipt and admission form dialogs are 920x740 and 960x760. Their document
previews and customization panels depend on fixed sheet widths and dense
toolbar controls.

Recommended improvements:

- Use adaptive minimum sizes instead of fixed 920px/960px defaults.
- Add high-contrast preview zoom controls and fit-to-width mode.
- Separate print/export actions from customization controls.
- Add an unsaved-template indicator and confirm before closing changed
  customizations.
- Preview whether page margins and dual-copy mode fit one A4 sheet.
- Preserve custom layout scroll state while switching tabs.

### Priority 10: Admission customization is too dense

**Evidence:** `app/ui/print_dialogs.py:565-765`

The admission template tab combines rich-text editing, title/subtitle,
custom fields, terms, declarations, and save actions in one view.

Recommended improvements:

- Split customization into Template, Fields, and Signatures tabs.
- Use a small preview pane or live preview instead of two separated workflows.
- Reduce the number of always-visible controls.
- Provide undo/reset actions next to the relevant field group.
- Define recommended max lengths and live character counts for document text.

### Priority 11: Update dialogs mix security and UX weakly

**Evidence:** `app/ui/app_update_dialog.py:96-167`,
`app/ui/app_update_dialog.py:208-257`,
`app/ui/app_update_dialog.py:291-367`

The update dialog clearly shows current and latest versions and has a
download progress area, but the primary action, release notes, GitHub link,
and reminder state have inconsistent importance.

Recommended improvements:

- Group actions into "Later," "View Release," and "Download and Update."
- Show update size and download/installation state clearly.
- Add checksum/signature verification feedback before launch.
- Disable the update button while downloading and cancel cleanly.
- Explain whether the app closes or restarts after installation.
- Replace emoji icons with consistent SVG symbols.

### Priority 12: Messaging settings are too long and too complex

**Evidence:** `app/ui/messaging_settings_widget.py:342-425`,
`app/ui/messaging_settings_widget.py:456-520`,
`app/ui/messaging_settings_widget.py:684-901`

Messaging configuration has provider credentials, templates, automation,
queue limits, diagnostics, and footer actions. The provider credentials tab
combines environment, IDs, secure token storage, testing, and helper text.

Recommended improvements:

- Split credentials and operational settings into a guided setup flow.
- Add connection status and a final test step in the provider tab.
- Mask and validate IDs before API calls.
- Use a dedicated token replacement dialog instead of embedding a password
  field in the main settings panel.
- Add unsaved-change state and confirmation before leaving changed settings.
- Keep Test Connection and Save Settings visually distinct.
- Warn more prominently before switching Production to Development or vice
  versa.

### Priority 13: Diagnostics need structured outcomes

**Evidence:** `app/ui/messaging_settings_widget.py:684-901`,
`app/ui/settings_dialog.py:1271-1422`

The messaging and maintenance areas contain logs and operation output. Raw
status text can be hard to scan when many settings and diagnostics are shown.

Recommended improvements:

- Separate health indicators, activity logs, and maintenance actions.
- Use labeled success, warning, and error components instead of raw text.
- Add copy/export actions for diagnostic summaries.
- Redact credentials and recipient identifiers in exported diagnostics.
- Add timestamps and a last-checked label to health cards.

### Priority 14: Explicit accessibility metadata is rare

The repository uses few explicit `setAccessibleName`,
`setAccessibleDescription`, or `setWhatsThis` calls. Apart from selected
tooltips in analysis, fees, results, teaching, students, and printing, most
icon-only and complex controls rely on visual text alone.

Recommended improvements:

- Add accessible names to settings, navigation, icon-only table actions,
  chart widgets, bulk-operation controls, and print controls.
- Add accessible descriptions to status colors and destructive buttons.
- Expose table selection and action state to screen readers.
- Add chart summaries as text for the same data shown visually.
- Test keyboard focus for every dialog and context menu.

### Priority 15: Tables use text for operations that should be standardized

**Evidence:** `app/ui/mixins/attendance_mixin.py:425-451`,
`app/ui/mixins/results_mixin.py:538-576`,
`app/ui/mixins/expenses_mixin.py:388-477`,
`app/ui/mixins/teaching_mixin.py:416-528`

Different modules use plain text status items, QTableWidget cell buttons,
small badges, and action links. Table action density and hit targets vary.

Recommended improvements:

- Standardize row action hit areas to at least 32px high.
- Use icons plus text or a single overflow menu instead of 3 to 5 actions.
- Right-align numerical columns and center date/status/ID columns.
- Keep action columns fixed at the right edge.
- Use consistent status badges across all modules.
- Add selected-row actions in a footer or inspector where practical.

## Remaining Dialog Flow Validation Checklist

- Attendance: batch/date first, unsaved-state warning, mark present/absent,
  save, override, and clear-all flows.
- Results: create test, enter all marks, partial marks, out-of-range marks,
  edit, delete, and confirm flows.
- Fees: generate, preview, duplicate detection, pay, edit, receipt, and
  reversal flows.
- Expenses: add, pay, partial payment, overdue, reverse, and delete flows.
- Teaching: plan, edit, record class, add homework, complete, cancel, and
  delete flows.
- Bulk students: search, filter, select visible, transfer, status lifecycle,
  cancel, and apply-confirmation flows.
- Printing: empty student selection, student selection, blank form, PDF
  export, print, and customized-template flows.
- Update: available update, release notes, download, cancel, checksum failure,
  install, and launch flows.
- Messaging: setup, replace/remove token, test connection, send test,
  template, automation, queue limits, and diagnostics flows.
