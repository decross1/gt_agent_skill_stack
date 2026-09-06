# Browser startup and failure checks

Dashboard and Graph load their four classic JavaScript dependencies with
`defer`, retaining their execution order. The existing inline program can then
show loading status and start a five-second readiness deadline while downloads
are pending. Application initialization reads the dependency globals only after
`DOMContentLoaded` (or immediately for an already-complete document).

A dependency deadline or a page departure during startup is terminal for that
document: an alert explains the failure and asks for a reload. A later download
or readiness callback cannot start the application or its API refresh loop.
Startup listeners/timer are removed on settlement. A monotonic-clock check on
readiness and visibility prevents a throttled timer from allowing late startup.
After successful startup, the existing source deadlines and page refresh
visibility/pagehide/pageshow behavior remain unchanged.

Both pages request the shared UI script through a URL containing its exact
SHA-256. Changing `ui.js` requires updating both URLs; a regression verifies the
identity. Reloading the updated HTML obtains the matching dependency without
global browser-cache clearing. Missing or incompatible required interfaces and
synchronous initialization exceptions remain explicit failures.

## File mode and source truth

`file:` pages still load saved JavaScript projections and do not start API
polling. Graph retains its minimal saved-data renderer when the shared UI file
is absent in file mode; its status explicitly disables live refresh/source
checks. Invalid or absent saved map data is labeled unavailable. HTTP(S) Graph
requires the shared UI and map renderer and fails explicitly if either is
missing. No unavailable projection is replaced with fabricated data or counts.
Activity and the shared UI implementation are unchanged by this startup gate.

## Validation

Run the focused offline tests from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  python3 -m pytest -q -p no:cacheprovider \
  tests/test_boot_deadline.py tests/test_dashboard_boot.py \
  tests/test_ui_data_provenance.py tests/test_dashboard_usability.py
```

`tests/browser_boot_probe.py` is a separate finite Firefox/WebDriver probe.
Use its `--help` for explicit source, archived snapshot and output paths. It
requires an existing normal Firefox, geckodriver and Node installation; it does
not install dependencies or restart the Brain service. Each browser session
uses private profiles and distinct WebDriver/WebSocket ports. The probe records
actual navigation, console/network events and screenshots without calling
application render functions or injecting projection globals.

Graph success in HTTP, file mode and the saved-only fallback requires the
renderer-owned `canvas.__brainmap` marker captured as `canvas.rendererMounted`.
A default nonzero canvas, valid data and a hidden empty-state note do not prove
that the renderer mounted. The marker records a completed mount; it is not a
pixel-correctness, authenticated-identity or scientific-validation claim.

`metadata.json` separates the executing probe's `runner.path` and `runner.sha256`
from the tested checkout's `source_head`, copied `source_assets` hashes and
private `fixture_assets` hashes. The runner fingerprint reads its own file before
browser startup. It is a local file identity, not signed execution attestation;
keep that file fixed during a run and preserve any wrapper separately.

A successful `--phase baseline --case normal` records `baseline-observed`.
`baseline-red-reproduced` requires at least one observed held-resource transition
from unchecked to a terminal result after release, and no failed case or probe
error. A loading label after release is not terminal. Normal-only or synthetic
pagehide-only observations cannot establish that a parser-blocking hold was
reproduced; a mixed run with a failed hold remains `not-established`. These labels
describe the evidence collected, not a requirement to make every baseline fail.

A hanging-resource fixture must hold a response longer than the startup
budget, sample the visible failure, then release it and verify the failure
remains terminal with no API requests. Test every dependency on both pages,
normal automatic boot, missing/stale UI, file mode and departure during startup.
Preserve raw negative receipts; a browser-driver/port failure is not evidence of
a product regression. Full repository tests need explicitly declared private
consumer and sibling proposal fixtures; missing-input skips are not a complete
validation result. Do not publish those private fixtures or reports.

## Limits

The five-second budget starts when the inline startup program executes. It does
not time the initial HTML or stylesheet response and cannot preempt parsing or
synchronous JavaScript execution. A background browser can delay timer dispatch;
the next readiness/visibility callback still checks the elapsed deadline before
starting the application. Late deferred scripts may finish executing after a
terminal failure, but application startup and refresh remain disabled. This is
not a network-cancellation or arbitrary-script sandbox claim.

A successful Linux Firefox fixture or LAN observation does not establish a
particular Windows client's cause or resolution. No service restart, binding,
automation, runtime authority or scientific-policy change is part of this code.
