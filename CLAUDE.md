# rift-nexus

See @README.md for project overview.

Architecture, package boundaries, and dependency graph: @docs/architecture.md
Design decisions and rationale (read before questioning an existing choice): @docs/decisions.md
Current task list: @TASKS.md

## Working conventions

- Target Python 3.14. PySide6 (Qt6) for `login` and `client` GUIs.
- pytest for tests, mirroring the `src/rift/<package>` layout under `tests/`.
- `protocol`, `mapdb`, and `pkgmanager` have no live-connection dependency — keep it that way. Build and test them against static/recorded data only.
- `engine` and `login` are mutually independent; `client` depends on both being functional. Respect this order unless `docs/decisions.md` is updated to reflect a deliberate change.
- This is a rebuild, not a port. Never treat Ruby source (`lich-5`, `scripts`, `dr-scripts`) as executable reference or a conformance target — Python cannot run Ruby. Ruby source is read-only research input for API design (usage-frequency analysis), nothing more.
- Update @TASKS.md checkboxes as work completes. Log any nontrivial architectural or naming decision in @docs/decisions.md rather than only in commit messages.
- Files end with a single trailing newline (enforced via `.editorconfig`). Markdown/prose is not hard-wrapped at a fixed column — let paragraphs run long; wrap only at real semantic breaks (list items, headers, code blocks).

## Licensing & attribution

This project is original, MIT-licensed work. Every project listed under "Reference" or "Corpus" in `docs/architecture.md` is used for **behavioral and structural understanding only** — how the reference project models a problem, not its source code. Nothing here is to be copied, transliterated, or reproduced from those projects. If code written here would look recognizable to someone who's read the reference project's source, it needs to be rewritten from a description of *what it does*, not from the reference code itself.

Per-project status (verify before relying on any of this — licenses change, and this list is a starting point, not a guarantee):

- **`lich-5`** — BSD-3-Clause (confirmed). Read-only, non-executable static-analysis input only (usage-frequency counts). No source is copied; BSD-3 would require attribution if it ever were, but the point of this project is that it isn't.
- **`elanthia-online/scripts`, `dr-scripts`** — license **not yet confirmed**. Do not assume lich-5's BSD-3-Clause terms carry over. Read-only, non-executable static-analysis input only (usage-frequency counts); no source is copied.
- **`cartograph`** — MIT (confirmed, via its published gem). Only its MapDB *data format* is a compatibility target for `mapdb`. If any parsing logic is ever adapted from cartograph's actual code rather than written independently against the format spec, attribute it in a code comment and retain cartograph's copyright notice per the MIT license.
- **`jinx`, `jinxp`** — license **not yet confirmed**. Verify before treating their manifest format as a compatibility target for `pkgmanager`, and log the finding in `docs/decisions.md`.
- **Wrayth** — closed source. UX/behavior reference only, from observed in-game play — never source or binary. No implementation detail may originate from it.
- **Urnon, ProfanityFE** — open source; license **not yet confirmed**. Used for implementation *patterns* (how a problem is commonly solved), not for lifting code. Verify each project's actual license before adapting anything beyond a general approach, and attribute any nontrivial adapted technique in a code comment plus `docs/decisions.md`.
