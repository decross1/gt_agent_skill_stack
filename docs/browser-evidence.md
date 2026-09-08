# Browser navigation evidence

`tests/browser_navigation.py` is the supported local Firefox boundary for
finite navigation checks. It talks directly to geckodriver's W3C HTTP API and
uses only the Python standard library. Selenium and a WebDriver BiDi client are
not required.

The boundary keeps four observations separate:

1. Navigate with the ordinary W3C URL command and `pageLoadStrategy=normal`.
2. Wait for a small `document.readyState === "complete"` object.
3. Find a currently displayed element and click its fresh W3C element ID.
4. Poll a caller-supplied, size-capped state object until it is stable.

Each geckodriver owns distinct loopback WebDriver, Marionette, and BiDi ports.
The BiDi port is explicit even when no BiDi client is used, so concurrent runs
cannot collide on geckodriver's default port 9222. Each run also gives
geckodriver a newly created private profile root and deletes only that root and
its own process during cleanup.

Run the ordinary-page smoke before a product fixture:

```bash
python3 tests/browser_navigation.py --smoke \
  --output /tmp/browser-navigation-smoke \
  --profile-parent /home/USER/snap/firefox/common
```

The output receipt records the exact program, argv, Firefox/geckodriver
versions and capabilities, ports, profile, W3C commands, visible element ID,
click, stable state, screenshots, fixture requests, and cleanup. A successful
smoke does not qualify any product behavior.

Fault injection belongs in a separate finite fixture. Load the page normally,
pass the document barrier, then wait for the fixture to report that its delayed
requests arrived. Query only the nodes and fields needed by the acceptance
criteria; do not return every map row or force layout across a whole list.
Release delayed responses only after the recorded W3C action. Require both
responses to finish before reading final state.

Historical evidence remains distinct. AS038's browser result is 21/22 with its
required click unexecuted. AS039 returned a null first state and executed zero
checks, clicks, and screenshots. AS040's guarded wait passed six offline cases,
but its browser run returned `NS_ERROR_OUT_OF_MEMORY` from Marionette's
`evalInSandbox`; its geckodriver log also recorded the all-row visibility script
terminating by timeout. The exact-source 1002-test receipt is source evidence,
not a substitute for browser navigation evidence.
