# Architecture

## Purpose

Rift is a ground-up Python reimplementation of the lich-5 ecosystem's
*functionality* for Simutronics' text-based games (GemStone IV, DragonRealms).
It is explicitly **not a port**: lich-5 scripts are Ruby source executed as
Ruby threads with an injected runtime API, and Python cannot execute that
source. Every design decision here is driven by understanding *what* the
reference ecosystem does and *why*, then rebuilding it idiomatically in
Python.

* Primary goal: evaluate whether a Python rewrite is a viable, genuinely usable alternative to the Ruby-based lich-5 ecosystem — not a permanent sandbox — partly motivated by Python's more mature/accurate AI-assisted tooling compared to Ruby.
* Secondary goal: a learning vehicle for Python.

## Package layout

One repository, six internal packages under `src/rift/`, with enforced
import boundaries rather than free cross-imports:

```
rift/
├── protocol/     # game feed parsing
├── engine/       # scripting API + execution runtime
├── mapdb/        # room graph + pathfinding
├── pkgmanager/   # script repo client (install/update)
├── login/        # EAS authentication + session handoff
└── client/       # independent game front-end
```

## Dependency graph

```
        [protocol]              [mapdb]           [pkgmanager]
             |                     |                    |
             |          (no live connection required for any of these three —
             |           testable via static/recorded data alone)
             |
        +----+----+
        |         |
    [engine]   [login]  <-- also no live connection required to build/test
        |         |          its structure; live connection only needed
        |         |          to exercise a real auth flow
        +----+----+
             |
         [client]   <-- genuinely downstream: needs a live connection
                        (from login) and structured events (from protocol)
                        to have anything to render
```

Key implication: `protocol`, `mapdb`, and `pkgmanager` have **no dependency
on each other or on anything else**, and can be built and unit-tested first,
in any order, using static/recorded data. `engine` and `login` are mutually
independent and can proceed in parallel. `client` is the only package with a
hard dependency on other components being functional, and should be built
last.

## Package responsibilities

### `protocol`
Parses the Simutronics game stream (XML-like tags: room data, health,
combat, text) into structured events. This is the shared foundation both
`engine` and `client` consume as peers — neither depends on the other.
Testable entirely against recorded session logs; no live connection needed.

**Reference:** `elanthia-online/lich-5` (parser/event-feed layer).

### `engine`
Loads and executes user scripts, exposing the scripting API those scripts
call against (equivalent of lich5's injected globals: `waitrt?`, `fput`,
hooks, etc.). Consumes `protocol`'s event stream.

**Reference:** `elanthia-online/lich-5` (execution runtime).
**Corpus (read-only, non-executable):** `elanthia-online/scripts`,
`dr-scripts` — real-world Ruby scripts. Used *only* as static-analysis
input (e.g., frequency count of which Lich globals/methods appear across
the corpus, to prioritize what `engine`'s API needs first). Never treated
as executable test input — Python cannot run Ruby, so there is no
"does this script run against our engine" conformance test. Correctness
for `engine` comes from Python scripts written against its own API,
checked against behavior defined independently of the Ruby corpus.

### `mapdb`
Room-graph data and pathfinding (`;go2` equivalent). Static reference data;
no live connection required to build or test.

**Reference:** `elanthia-online/cartograph` (MapDB sync/diff tooling).

### `pkgmanager`
Repo client for installing/updating scripts from a script repository. No
live game connection required — only a repo URL.

**Reference:** `elanthia-online/jinx` (client), `elanthia-online/jinxp`
(repo packaging tool).

### `login`
Authenticates against Simutronics' EAS (Eaccess Authentication Server),
handles character/server selection, and hands off a session to `client`.
Independent of `engine` and `protocol` — it's a credential/session broker,
not a stream consumer.

**GUI:** PySide6.

### `client`
Independent front-end, target UX parity with Wrayth (closed source —
reference for behavior/UX only, not implementation). Implementation
approaches drawn from open-source references.

**References:** Urnon, ProfanityFE (open source — implementation
patterns for protocol handling and rendering).
**GUI:** PySide6.

## Testing philosophy

- `protocol`, `mapdb`, `pkgmanager`: unit-testable in isolation using
  static or recorded data. No live connection, no GUI dependency.
- `engine`: validated using Python scripts written against its own API,
  with expected behavior defined independently. The Ruby corpus informs
  API *shape* (what to prioritize); it cannot validate an *implementation*
  of that API, since nothing here executes Ruby.
- `login`, `client`: require integration-level testing against a live or
  simulated connection once `protocol` and `login` are stable.

## Out of scope (for now)

- Packaging/distribution, installers — revisit once all six packages
  exist in a working state.
- Consuming real jinx-formatted repos via `pkgmanager` — only relevant
  if compatibility with the existing script ecosystem's distribution
  format becomes a goal.