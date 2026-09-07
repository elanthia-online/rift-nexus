# Decisions

Running log of choices made and why. Newest at bottom. Not formal ADR numbering — a solo project doesn't need the ceremony, just the record.

---

## Scope & framing

**Not a port.** lich-5 scripts are Ruby source executed as Ruby threads with an injected runtime API. Python cannot execute that source. This project rebuilds the *functionality* idiomatically in Python; it does not translate Ruby syntax line-by-line. Corollary: the Ruby script corpus (`scripts`, `dr-scripts`) can never be used as executable conformance test input — there is no "does this real script run against our engine" check possible. It is read-only research material for API design (what globals/methods real scripts actually call, and how often), nothing more.

**Primary goal is evaluating whether a Python rewrite is a viable, genuinely usable alternative** to the Ruby-based lich-5 ecosystem — partly motivated by Python having more mature/accurate AI-assisted tooling than Ruby. Secondary goal is a learning vehicle for Python.

## Stack

- **Python 3.14** — current stable release at time of decision (3.15 was alpha-only).
- **PySide6** (Qt6) for `login` and `client` GUIs, chosen over Tkinter. Reasoning: lich5's own login manager is a GTK3 app — a real toolkit with native list/tree widgets, not a simple form. PySide6 gets closer functional parity and is a more broadly transferable skill than Tkinter.
- **pytest** — confirmed. Wired into `pyproject.toml` (`dev` extra plus `[tool.pytest.ini_options]` with `testpaths`/`pythonpath` set for the `src/` layout).

## Repository & package structure

**One repo, six internal packages, not six separate distributed packages.** Full separation (independently versioned/installable packages) was considered and rejected for now: correct package boundaries aren't yet known this early, and premature boundaries are often wrong boundaries. A true monolith was also rejected: it would blur genuinely different concerns (pure parsing logic vs. GUI code) and would teach less about Python's module/package system, which is itself a stated learning goal. Chosen middle ground: one repo, enforced import boundaries between packages, `src/` layout (catches packaging mistakes early by preventing accidental imports from the working directory instead of the installed package).

**Six packages:** `protocol`, `engine`, `mapdb`, `pkgmanager`, `login`, `client`. See `docs/architecture.md` for responsibilities and the dependency graph. Key finding: `protocol`, `mapdb`, and `pkgmanager` have no live-connection dependency and can be built/tested first, in any order; `engine` and `login` are mutually independent; `client` is the only package genuinely downstream of the others.

## Component 3 (`client`) scope

Confirmed as an independent, full game client — not a proxy requiring an external front-end. Target UX parity: Wrayth (closed source — reference for behavior/UX only). Implementation-level references: Urnon and ProfanityFE (both open source, inspectable).

## Naming

- **Package namespace:** `rift`. GemStone IV lore tie: the Rift is the in-game location spirits of the dead pass through — apt metaphor for "same functional intent, entirely new substrate."
- **Repository name:** `rift-nexus`. Considered and rejected: `project-rift` (too generic, reads as placeholder), `rift-lab` / `rift-sandbox` (accurately describes the project's actual nature — primarily a learning sandbox — but undersells intent; the name needed to read as a serious, fully-formed replacement, not a labeled experiment), `rift-portal` (good multi-component-entry-point framing, but "portal" carries generic SaaS/product-dashboard connotations). `rift-nexus` chosen for reading as intentional/permanent while still accurately describing the repo as a convergence point for multiple components. Note: this is a naming-merit choice, not a confirmed GS4-lore tie — no established in-game link between "the Rift" and "a Nexus" was confirmed.
- **License:** MIT.

## Tooling workflow

- Architecture/naming/tradeoff decisions handled conversationally (this chat), not in Claude Code — better suited to open-ended reasoning and web research than an agentic edit/run/verify loop.
- Migration to Claude Code (VS Code) planned for once `architecture.md`, `decisions.md`, `TASKS.md`, and `CLAUDE.md` exist alongside the skeleton package directories — i.e., once there's a real codebase with real context files for its memory system to load, and the work becomes actual implementation rather than planning.
- `CLAUDE.md` is committed to source control (not gitignored) — it's project memory, shared team/self context. Personal-only preferences belong in `~/.claude/CLAUDE.md` via `@import`, not in a repo-local file (`CLAUDE.local.md` is deprecated for this reason).
