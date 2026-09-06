# Brain deployment and restart

The user-level Brain service serves the existing dynamic Brain backend from the
canonical checkout on `0.0.0.0:5180`. It retains the server's current data,
static-asset, and governed proposal-write routes; this deployment layer does not
add API routes, credentials, authentication, or runtime-agent authority.

## Deployment contract

`brain-deploy.path` watches both the loose `main` ref and its reflog. Its helper
restarts `brain.service` only when all of these hold:

- the configured source is the Git top-level checkout;
- the checked-out branch is `main` and `HEAD` matches `refs/heads/main`;
- no Git index lock or staged change is present, and guarded source is clean; and
- the committed runtime-source fingerprint differs from the last successful deployment.

The helper holds an advisory state lock while checking and restarting. It checks
the source again immediately before and after restart, and records the new
fingerprint atomically only after `brain.service` reports active, bounded
read-only GET checks confirm supported summary and operations responses, and a
second active check passes after those probes. The HTTP responses are not bound
to systemd's `MainPID`: this sequence detects the managed service exiting during
the probes, but does not prove that `MainPID` served each response.

The applied-runtime fingerprint hashes committed files under `scripts/` and
`memory/brain/view/`. Unit templates under `systemd/user/` remain in the dirty
source guard, but the helper neither installs them nor includes them in the
fingerprint. A committed unit-template-only change therefore does not restart
Brain or imply that the installed unit changed. Unstaged operator guidance,
private ledgers, handoffs and ignored generated snapshots are data or
maintenance context, not imported runtime source, and remain untouched. Any
staged change anywhere in the repository, including a staged non-runtime file,
still defers deployment; no-applied-runtime-change commits do not restart it.
Reflog/ref duplicates and unrelated file or ledger writes therefore do not
restart Brain.

If a source guard is busy or dirty, the watcher exits successfully without a
restart or state write; a later clean `main` ref update is the recovery trigger.
Clearing a staged non-runtime change without another ref update does not retrigger
the path unit. If no later ref update is expected, invoke the helper once
manually after the source and index are clean. Its durable state lives outside
the checkout so recording a fingerprint never makes the watched source dirty.
If restart fails, the old fingerprint remains durable, while `brain.service`
uses systemd's `on-failure` restart with a 15-second delay and a three-attempt,
five-minute start limit. Logs append to dedicated `run_state/brain-*.log` files
and do not replace existing audit logs.

The deploy service executes `scripts/brain_deploy.py` from the writable checkout.
Python starts that file before its in-process Git self-check can run, so the
guards cannot prevent modified top-level helper code from executing. Treat a
reviewed, clean helper as an installation and operating precondition; these
guards do not establish a trusted entrypoint.

## Parent installation

These units assume the canonical checkout is `%h/projects/agent_system`. Install
them only after runtime source and the index are clean, `HEAD` is the intended
local `main` commit, and the parent has stopped the old manual process using its
approved procedure. Installation is the explicit copy below; the deploy helper
does not copy or reconcile unit files.

```sh
source_root="$HOME/projects/agent_system"
install -Dm0644 "$source_root/systemd/user/brain.service" "$HOME/.config/systemd/user/brain.service"
install -Dm0644 "$source_root/systemd/user/brain-deploy.service" "$HOME/.config/systemd/user/brain-deploy.service"
install -Dm0644 "$source_root/systemd/user/brain-deploy.path" "$HOME/.config/systemd/user/brain-deploy.path"
systemctl --user daemon-reload
systemctl --user enable brain.service
systemctl --user start brain-deploy.service
systemctl --user enable --now brain-deploy.path
```

The first helper invocation starts the service from the newly deployed source and records its fingerprint only after API readiness. Check operation with:

```sh
systemctl --user status brain.service brain-deploy.path
tail -n 80 "$HOME/projects/agent_system/run_state/brain-systemd.log"
tail -n 80 "$HOME/projects/agent_system/run_state/brain-deploy.log"
```

`install` copies the three templates into the user manager's configuration.
`systemctl --user daemon-reload` makes systemd read those copies but does not
start or restart a unit. `systemctl --user start brain-deploy.service` runs the
one-shot helper once, while `systemctl --user enable --now brain-deploy.path`
enables and starts ref-event monitoring. For later unit template changes, copy
the changed templates again and run `daemon-reload`; restart an affected running
`brain.service` or `brain-deploy.path` explicitly. A reloaded
`brain-deploy.service` definition applies on its next invocation.

For a clean-source recovery with no new `main` ref update, run `systemctl --user start brain-deploy.service` once after resolving the guard or failure. A deferred check does not queue a recurring retry.

To change the canonical checkout location, update all three installed unit
files consistently, run `systemctl --user daemon-reload`, and perform another guarded deployment. The provided readiness probes target the existing loopback address on port 5180; changing that port requires a separately reviewed helper/unit update.

Before initial cutover, verify the old PID file, process command and cwd still identify the existing Brain server. Stop only that confirmed process. Do not run `serve_brain.sh start` alongside the unit: it would create a second manager and performs a model-catalog preflight. Preserve the prior PID/log and source revision as evidence. If deployment fails, retain the old fingerprint, inspect the bounded service logs and recover with the reviewed source; do not overwrite dirty source or reset history. Unit changes require explicit installation and daemon-reload; the path helper does not rewrite installed units.
