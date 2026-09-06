# Brain deployment and restart

The user-level Brain service keeps the existing backend on `0.0.0.0:5180` with
the canonical checkout as its working directory and virtual module root. Its
data, generated static view, local-model calls, read-only GET routes, and
governed proposal writes retain their current paths and behavior. Deployment
adds no API, credential, authentication claim, model call, or runtime-agent
authority.

## What is trusted and applied

Both systemd entrypoints run the same reviewed launcher installed at
`%h/.local/lib/brain-server/brain-launch.py` under Python isolated mode. Neither
unit executes Python from the writable checkout directly. In `deploy` mode the
launcher checks the canonical `main` checkout before loading candidate code,
creates a private immutable raw-Git snapshot, stages (but does not promote) a
selector candidate, and executes that snapshot's pinned `brain_deploy.py`. In
`serve` mode it admits the selected manifest again on every start, including a
systemd restart-on-failure, before running the pinned server with its virtual
`__file__` at the canonical path. That compatibility keeps the backend's
`ROOT`, mutable ledgers, generated view, and child CLI paths canonical without
changing `brain_server.py`.

The launcher descriptor is a canonical schema-1 JSON manifest plus an
out-of-band whole-file SHA-256. It binds the full 40-character commit, branch,
canonical source, release and snapshot roots, ordered raw runtime records and
their aggregate fingerprint, installed launcher path and bytes, and exact serve
and deploy entrypoints. The deployment helper rechecks the descriptor hashes,
fixed `0.0.0.0:5180` serve argv, canonical cwd, installed launcher bytes, and
the caller's exact source, helper-state, selector, and `brain.service` values
against the deploy entrypoint before any manager command or state write. The
launcher's outer lock serializes prepare, candidate staging, helper execution,
and selector resolution. The helper takes a distinct state-file lock as defense
against a second direct helper invocation; it never reacquires the launcher
lock.

An applied fingerprint consists of:

- the raw committed runtime fingerprint for `scripts/` and
  `memory/brain/view/` in the admitted release;
- the actual separately installed launcher path and SHA-256; and
- the installed definitions returned for `brain.service`,
  `brain-deploy.service`, and `brain-deploy.path`, only while systemd reports
  `NeedDaemonReload=no`.

Repository unit templates are guarded installation inputs, not evidence of
installed units. A commit changing only a unit template cannot claim adoption.
After copying a changed template, deployment defers until an explicit
`daemon-reload`; its installed identity then changes the applied fingerprint.
The helper fingerprints the definitions systemd actually reports, but it does
not interpret every unit directive as policy. Exact reviewed installed unit
bytes and the host plan's checks of fragment paths, empty drop-ins, restart and
start-limit settings, and all watched paths are ongoing preconditions. A new
installed-definition hash proves a byte change; it does not approve that
change's semantics.
Documentation, operator files, handoffs, and mutable brain ledgers are excluded
from the runtime fingerprint. Changes to them neither select new runtime bytes
nor restart Brain. A commit with identical runtime and installed identities is
a qualified no-op: the helper verifies the current service but does not restart
it or replace its applied process receipt. This remains true if systemd already
replaced the recorded PID during a bounded restart-on-failure.

The launcher owns the source guards: top-level checkout, `main`/`HEAD` identity,
index lock, staged changes, raw committed blobs, and runtime/launcher-template
dirt. Canonical non-runtime operator and ledger changes remain untouched. A
guard deferral exits with status 20, makes no selector promotion, and causes no
service action. `brain-deploy.service` lists 20 as a successful one-shot status
so the path watcher can rearm; the launcher log still reports the deferral.
Invalid manifests, state, or configuration exit 21 and remain failures.

## Process-bound readiness

For a changed applied fingerprint, the helper records the pre-restart systemd
identity and issues one `systemctl --user restart brain.service`. It accepts a
deployment only after one bounded observation proves all of the following:

1. systemd reports `active/running`, a different positive `MainPID`, and a newer
   `ExecMainStartTimestampMonotonic`;
2. `/proc/<MainPID>` supplies a positive process start tick, the exact canonical
   cwd, and the exact serve argv from the hash-pinned manifest;
3. all IPv4 and IPv6 listening rows for port 5180 contain exactly one listener,
   it is the expected `0.0.0.0:5180` socket, and that socket is held only by the
   selected `MainPID` among inspectable processes;
4. proxy-disabled, redirect-rejecting loopback GETs return HTTP 200 and the
   existing supported `/api/summary` and `/api/operations` object shapes, with
   each response capped at 8 MiB; and
5. systemd identity, process start ticks/cwd/argv, and listener ownership are
   unchanged when checked again after both GETs.

Only then does an atomic mode-0600 state write expose the candidate manifest
SHA-256 at top level for launcher promotion. Restart, timeout, dying-service,
identity, listener, API, or post-check failures preserve the previous applied
fingerprint/manifest and add a bounded failed-attempt receipt. The candidate is
not promoted. Readiness is a bracketed point-in-time proof; it cannot guarantee
what happens immediately afterward, but an old compatible responder or a
service that dies during the probes cannot advance state.

The helper accepts no readiness success after its 45-second deadline. Remaining
time is passed into systemd commands and HTTP calls; `/proc` tables and file
descriptor scans have byte/count limits and recheck the deadline between kernel
reads. A single kernel read is not interruptible by Python, so the oneshot's
`TimeoutStartSec=90s` is the outer transaction cap. The Brain unit retains its
existing 15-second on-failure delay and three starts per five minutes. The path
unit rate-limits event bursts. A failed or deferred event does not create a
background retry loop.

## Ref events and finite recovery

`brain-deploy.path` covers the loose `refs/heads/main` file, the main reflog, and
`packed-refs`. A packed-ref rewrite can also concern another branch, and Git may
emit several loose/ref/reflog events for one operation; the launcher's exact
main and runtime checks reduce those to a no-op. Writes to docs, ledgers, and
other unwatched files do not create ref events.

Clearing an index lock, staged non-runtime change, or runtime dirt does not
itself touch a watched ref. After fixing the guard, either wait for the next real
main ref update or make one finite manual check:

```sh
systemctl --user start brain-deploy.service
```

Inspect its single result before doing anything else. Do not wrap that command
in a retry loop. A manual successful fallback does not retroactively prove that
an earlier automatic event succeeded.

## Explicit reviewed installation and cutover

These commands are an operator procedure for an already reviewed exact release.
They are not run by the deployment helper, launcher, or path unit. Confirm the
reviewed source commit and expected hashes first; substitute the recorded hashes
from that review rather than trusting values computed only after copying.

```sh
source_root="$HOME/projects/agent_system"
launcher_source="$source_root/systemd/libexec/brain-launch.py"
launcher_installed="$HOME/.local/lib/brain-server/brain-launch.py"
unit_root="$HOME/.config/systemd/user"
state_root="$HOME/.local/state/brain-server"

git -C "$source_root" rev-parse HEAD
git -C "$source_root" status --short --branch
sha256sum "$launcher_source" \
  "$source_root/systemd/user/brain.service" \
  "$source_root/systemd/user/brain-deploy.service" \
  "$source_root/systemd/user/brain-deploy.path"

install -d -m 0700 "$HOME/.local/lib/brain-server" "$state_root"
install -Dm 0755 "$launcher_source" "$launcher_installed"
install -Dm 0644 "$source_root/systemd/user/brain.service" "$unit_root/brain.service"
install -Dm 0644 "$source_root/systemd/user/brain-deploy.service" "$unit_root/brain-deploy.service"
install -Dm 0644 "$source_root/systemd/user/brain-deploy.path" "$unit_root/brain-deploy.path"

cmp "$launcher_source" "$launcher_installed"
cmp "$source_root/systemd/user/brain.service" "$unit_root/brain.service"
cmp "$source_root/systemd/user/brain-deploy.service" "$unit_root/brain-deploy.service"
cmp "$source_root/systemd/user/brain-deploy.path" "$unit_root/brain-deploy.path"
sha256sum "$launcher_installed" "$unit_root/brain.service" \
  "$unit_root/brain-deploy.service" "$unit_root/brain-deploy.path"

systemctl --user daemon-reload
systemctl --user enable brain.service
```

`install` only copies reviewed bytes. `daemon-reload` only makes the user
manager read those installed definitions. `enable brain.service` only creates
future-start links; none of these commands cuts over the listener.

Before the controlled cutover, capture the existing manual server's exact PID,
`/proc` start ticks, argv, cwd, port-5180 socket inode, log/PID files, and known
good source/manifest identity. Recheck them immediately before stopping only
that process by the separately reviewed host plan. Then run exactly one initial
deployment and arm the watcher only after the deployment passes:

```sh
systemctl --user start brain-deploy.service
systemctl --user status brain.service brain-deploy.service --no-pager
systemctl --user enable --now brain-deploy.path
systemctl --user status brain.service brain-deploy.path --no-pager
```

Inspect the finite process/listener/API receipts and the two append-only service
logs. Do not run `serve_brain.sh start` beside systemd; it is a second process
manager and its model-catalog preflight is outside this deployment path.

Later source changes require no unit copy. Later launcher or unit changes are
not auto-adopted: review the exact bytes, repeat their explicit `install` and
hash/`cmp` checks, run `daemon-reload`, and invoke one controlled deployment.
Changing the canonical source path, state path, host, port, interpreter, or unit
arguments requires another reviewed launcher/unit update.

If deployment fails after the restart command, the candidate process may still
be running even though the candidate selector is removed, the prior selector is
restored, and the prior applied receipt remains. Those selector and receipt
actions are not a process rollback. Inspect the live `MainPID`, start ticks,
argv, cwd, and port ownership; stop only the identified candidate through the
reviewed host recovery procedure, then perform one verified manual recovery.

An older selected release also cannot simply be started after the checkout's
runtime changes: the launcher's current-source fingerprint guard rejects a
release whose runtime fingerprint differs from the current clean source. A
known-good manual invocation or release therefore requires the predeclared
host recovery procedure and revalidation of its source hash, argv/cwd, and port
ownership. Do not edit selectors, overwrite dirty source, reset Git history, or
loop restarts as an improvised rollback.

## Trust limits

The installed launcher, installed unit files, state directory, systemd user
manager, Git object store, kernel `/proc` observations, and same-UID ownership
are operating trust assumptions. The checks close the known order-of-execution
and unrelated-listener defects. They are not a sandbox against the same user,
cryptographic actor authentication, or a proof against every check/use race.
Installed-file and manager-definition checks are repeated around restart, but a
same-UID actor can still mutate accessible state between finite observations.
Keep `%h/.local/state/brain-server` mode 0700 and install only an exact reviewed
launcher and units.
