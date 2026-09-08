# rift-nexus

A ground-up Python reimplementation of the [lich-5](https://github.com/elanthia-online/lich-5) ecosystem's *functionality* for Simutronics' text-based games (GemStone IV, DragonRealms). This is explicitly **not a port** — lich-5 scripts are Ruby source executed as Ruby threads with an injected runtime API, and Python cannot execute that source. Every design decision here comes from understanding *what* the reference ecosystem does and *why*, then rebuilding it idiomatically in Python.

- **Primary goal:** evaluate whether a Python rewrite is a viable, genuinely usable alternative to the Ruby-based lich-5 ecosystem — not a permanent sandbox — partly motivated by Python's more mature/accurate AI-assisted tooling compared to Ruby.
- **Secondary goal:** a learning vehicle for Python.

## Package layout

One repository, six packages under `src/rift/`, with enforced import boundaries rather than free cross-imports:

- `protocol` — game feed parsing
- `engine` — scripting API + execution runtime
- `mapdb` — room graph + pathfinding
- `pkgmanager` — script repo client (install/update)
- `login` — EAS authentication + session handoff
- `client` — independent game front-end

See [docs/architecture.md](docs/architecture.md) for package responsibilities, the dependency graph, and testing philosophy.

## Getting started

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

For running the real `login` → `client` chain against a live account (not just the automated test suite), see [docs/usage.md](docs/usage.md).

## Documentation

- [docs/usage.md](docs/usage.md) — manual usage: running `login` and `client` against a live account
- [docs/architecture.md](docs/architecture.md) — architecture, package boundaries, dependency graph
- [docs/decisions.md](docs/decisions.md) — design decisions and rationale
- [TASKS.md](TASKS.md) — current task list
- [CLAUDE.md](CLAUDE.md) — working conventions and licensing/attribution policy
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) — third-party attribution tracking

## Status

Early scaffolding stage — see [TASKS.md](TASKS.md) for current progress.

## License

MIT — see [LICENSE](LICENSE). Reference projects consulted during development (lich-5, cartograph, jinx, Urnon, ProfanityFE, and others) are used for behavioral/structural understanding only, not as a source of copied code — see [CLAUDE.md](CLAUDE.md) for the full policy and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for attribution status.
