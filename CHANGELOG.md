# Changelog

All notable changes to Null's Addons are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Consolidated the per-module numeric-coercion helpers (`_num` / `_int` / `_f`)
  into a single `nulladdons.util` (`to_float` / `to_int`), so the finite-value
  guard lives in exactly one place.
- Modernized packaging metadata: PyPI classifiers, project URLs, a `py.typed`
  marker (PEP 561), and a Ruff lint configuration.

### Added
- **Fun, animations & effects** (`nulladdons/fx.py`): a spinner while the live
  Bazaar/election loads, an eased "slot-machine" count-up on the headline number
  in `plan` and `status`, sparkles, and a `HOT` / `CRACKED 🔥` flair tag on juicy
  flips (`flair.cracked_label`, parity with the mod). Everything is pure
  presentation — a count-up always lands on the exact value — and degrades to
  nothing when piped, under `NO_COLOR`/`TERM=dumb`, `--serious`, or the new
  `--no-anim` / `NULLADDONS_NO_ANIM`.
- **Mod HUD polish**: the top-flips panel fades in when it appears and its header
  gently pulses while a cracked flip is on the board, via a new pure, unit-tested
  `core/Anim.java` (easing, fade, pulse, ARGB alpha) shared by the Forge and
  Fabric loaders.
- `LICENSE` (MIT), `CHANGELOG.md`, `CONTRIBUTING.md`.
- GitHub Actions CI: the Python test suite on 3.9–3.13, a Ruff lint job, and the
  Java engine self-test.

### Fixed
- The hidden `lore` command no longer prints a literal `==SUPPRESS==` in
  `--help`; it's now cleanly undocumented (argparse doesn't honour
  `help=SUPPRESS` on subparsers).

### Removed
- Two dead imports (`mechanics` in `bazaar.py`, `minutes` in `brief.py`) and a
  few dead test imports; modernized file I/O and type-annotation style via Ruff.

## [1.0.0] — 2026-07-09

First complete release. A Hypixel SkyBlock money-making ecosystem that reads
live market data and hands you *direct, honest* commands — it advises, it never
automates gameplay.

### Bazaar flipping
- Live fetch from the public `/skyblock/bazaar` endpoint, with the notorious
  reversed `buy_summary` / `sell_summary` naming translated exactly once.
- Market-microstructure engine: bid-ask spread, moving-week liquidity,
  congestion-aware fill-time estimates, market-impact-aware position sizing,
  velocity (coins/hour), and a confidence score.
- Correctness guards learned the hard way: a max-margin ceiling, a max-spread
  outlier filter, and a minimum-liquidity floor to reject manipulated or
  too-good-to-be-true books.
- Accurate tax model (1.25%, 1.1% with a Booster Cookie), the 0.1 undercut
  increment, and the 71,680-per-order cap.
- Direct commands: "Buy N of X at price, wait ~M min, sell at price."

### Craft flipping & Magical Power
- Craft-flip finder that buys raw mats, applies a known recipe, and sells the
  output — gated by the same correctness guards.
- Personalized accessory craft/buy planner to raise Magical Power as cheaply
  and quickly as possible.

### Auction House
- Sale-price index built from the light `auctions_ended` feed, a rolling local
  log for median/last prices, your-own-listings summary (with a key), and a
  bounded BIN-flip scan honestly flagged as leads to verify.

### Ecosystem & personalization
- Per-account config (bankroll, risk appetite, goals) driving bankroll-scaled
  income projections and a unified `status` hub.
- Day-over-day progress snapshots (coins, skills, slayer, dungeons, collections,
  pets, fairy souls) diffed for the daily brief.
- Mayor/Election engine that folds active perks (e.g. Derpy's tax holiday) into
  the economics.

### Intelligence
- Daily brief: snapshots the account and market, hands the facts to a Gemini
  SkyBlock-expert model for a summary, and falls back to a deterministic local
  brief when the LLM is unavailable.
- Grounded `ask` command: retrieval-augmented Q&A over live data that answers
  "I don't know based on the current data" instead of hallucinating.

### Onboarding & delivery
- Interactive setup wizard and a `doctor` command with live API validation.
- Terminal UI helpers, Discord webhooks for crucial alerts, and an opt-in,
  toggleable personality layer (SkyBlock satire, easter eggs) that never touches
  the numbers — `--serious` / `NULLADDONS_SERIOUS` turns it fully off.

### Minecraft mods
- A pure Java-8 `core` economics port (compiled and self-tested, 44 checks),
  shared by two loaders: **Forge 1.8.9** and **Fabric 1.21.x**.
- Seamless surfaces: a movable top-flips HUD that only draws on SkyBlock, and
  live flip/craft numbers appended under item tooltips in Bazaar menus.
- Opt-in, off-by-default, PII-free telemetry.

### Quality
- 87 Python unit tests and the Java self-test, all green. Standard-library only
  (no runtime dependencies).

[Unreleased]: https://github.com/NullifiedUniverse/NulAddons/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/NullifiedUniverse/NulAddons/releases/tag/v1.0.0
