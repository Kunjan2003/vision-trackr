# Vision Tracker workspace redesign

Reference: https://www.timechamp.io/see-all-features and the Time Champ user-dashboard documentation. These inform the information hierarchy; this app remains a Windows desktop workspace with a local SQLite database.

## Delivered

- Rebuilt overview with working, productive, active time and productivity cards, equal-length period comparisons, daily goal, animated 3D focus graphic, stacked hourly activity, time breakdown and work trends.
- Shared light/dark design system across authentication, projects, focus, attendance, reports, settings and recovery screens. Sidebar remains accessible in narrow windows; motion respects the operating system's reduced-motion preference.
- Today, trailing seven days, month-to-date and custom date ranges (up to 93 days) for workspace analytics. CSV/PDF exports retain the selected reporting range. The activity explorer explicitly selects one day, with text search, category filtering and pagination.
- Period-wide app usage split by classification and captured website hostnames from the existing opt-in browser bridge. Window-title masking deliberately removes hostnames too.
- Daily timesheets with first/last session, active/idle/break time, overtime against the personal goal and offline time. Existing manual entry and idle recovery workflows remain available.
- Local invoices generated from project time and rates, scoped to a client and date range. Persisted immutable line items, duplicate-number protection, currency selection, draft/sent/paid/void states and downloadable PDF. Status changes are bookkeeping actions; the app does not send invoices or process payments. Amounts exclude tax.
- Existing projects, tasks, automatic project tagging, focus, calendar imports, backups, privacy controls and reports retained.

## Corrected defects

- Project and task accounting included the day after the selected end date; both now stop at the selected local midnight boundary.
- Daily exports omitted offline entries and did not escape formula-like spreadsheet cells; they now share the timeline used by the dashboard and escape untrusted CSV labels.
- Narrow-window navigation hid every inactive destination. Icon navigation now retains every destination with an accessible label and tooltip.
- Session actions are disabled while the service connects, rather than appearing ready before session state arrives.
- Removed the nonfunctional second-account registration switch on this single-account desktop installation.
- Prevented stale refresh responses from replacing data after a date change and split larger workspaces into lazy-loaded bundles.
- Floating-widget background is explicitly transparent and its buttons remain disabled until a live session state arrives.

## Feature coverage and remaining architecture

This is **not full Time Champ parity**. The desktop agent currently supports one local account, not a shared workforce service.

| Time Champ capability | Vision Tracker status |
| --- | --- |
| Automatic app time, idle, breaks, activity timeline | Available |
| Personal dashboard, trends and classification | Available; redesigned |
| Project/task management and billable time | Available |
| Personal attendance and timesheets | Available |
| Invoicing | Local records and PDF; no tax/payment provider |
| Calendar integration | Local ICS import; no provider synchronization |
| Teams, manager roles and cross-device dashboards | Requires an authenticated organization backend and agent synchronization |
| Timesheet approval, payroll and HR records | Requires organization roles, approval rules and payroll integration |
| Shift rosters and leave approvals | Not implemented |
| Screenshots, live screens, video/audio monitoring | Not implemented; existing agent records metadata only |
| GPS, geofences and field/mobile tracking | Requires mobile clients and a location service |
| USB/file monitoring, website blocking and DLP | Requires additional Windows policy/agent capabilities |
| Third-party integrations and scheduled email delivery | Not implemented |
| Attrition prediction | Not implemented |

## Verification

Run `PYTHONPATH=backend python -m pytest -q backend/tests --disable-warnings` and `cd desktop && npm ci && npm run build:ui`.

Regression coverage includes local-midnight clipping, adjacent-day exclusion from billing, manual time reconciliation, invoice snapshots, duplicate numbers, client ownership validation, invoice state transitions, PDF output and authenticated routes. Electron main/preload scripts are syntax checked.

Rendered-screen automation was blocked by automatic approval review of the browser installation in this environment. Native Windows foreground capture, tray integration and the packaged installer require Windows verification. Do not interpret a passing UI compilation as a completed Windows smoke test.
