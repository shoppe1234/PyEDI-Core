# Rules Management Fix — Task List

## Task 1: Onboard Wizard — Required Field Indicators
**File:** `portal/ui/src/pages/Onboard.tsx`

- [ ] Add red `*` asterisk to required field labels: Profile Name, Trading Partner, Transaction Type
- [ ] Add `* Required` footnote near top of form
- [ ] Add helper text below grayed-out "Next: Configure Rules" button: "Register your partner above before proceeding" (shown when `!success`)

## Task 2: Rules Page Fixes
**File:** `portal/ui/src/pages/Rules.tsx`

### 2a: Dropdown Truncation (FieldCombobox)
- [ ] Refactor dropdown list to render via `ReactDOM.createPortal()` into `document.body`
- [ ] Position dropdown using `getBoundingClientRect()` on the input element
- [ ] Add scroll/resize listener to reposition dropdown dynamically

### 2b: Field Clearing Persistence
- [ ] Add `previousValue` ref to FieldCombobox, captured on focus
- [ ] On blur, if value is empty and previousValue was non-empty, revert to previousValue

### 2c: Cancel Button for Rules Management
- [ ] Add Cancel button next to Save on Universal rules tab (re-fetches from API)
- [ ] Add Cancel button next to Save on Transaction rules tab (re-fetches from API)
- [ ] Add Cancel button next to Save on Partner rules tab (re-fetches from API)
