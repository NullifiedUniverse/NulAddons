# Contributing to Null's Addons

Thanks for wanting to help. This project has a small, sharp surface and a few
non-negotiable rules — read these first and the rest is easy.

## The golden rules

1. **Numbers are sacred.** Every profit figure, margin, fill-time, and
   recommendation must be correct and honest. If a market looks too good to be
   true, the engine's job is to *reject* it, not surface it. When in doubt,
   under-promise. The whole project exists because a single wrong recipe once
   printed a fake +49,454% craft — never again.
2. **Advisory only.** The tool reads public data and *suggests* trades. It never
   automates gameplay, sends inputs to Minecraft, or does anything that would
   break Hypixel's rules. Keep it that way.
3. **The personality never touches the numbers.** The flair layer (`flair.py`,
   `core/Flair.java`) may add jokes and labels around output, but it must never
   change a value. `--serious` / `NULLADDONS_SERIOUS=1` must produce fully
   neutral output.
4. **Don't hallucinate.** The `ask` command answers *only* from live data and
   says "I don't know based on the current data" otherwise. Preserve that.

## Python

Standard library only — no runtime dependencies. Target Python **3.9+**.

```bash
# Run the whole suite (87 tests):
python3 -m unittest discover -s tests

# Compile-check the package:
python3 -m compileall -q nulladdons
```

Style is enforced by [Ruff](https://docs.astral.sh/ruff/) (config in
`pyproject.toml`). If you have it installed:

```bash
ruff check nulladdons tests
```

Conventions used throughout:
- `from __future__ import annotations` at the top of every module.
- Defensive coercion of anything from the API via `nulladdons.util`
  (`to_float` / `to_int`) — never call `float()` on a raw API field.
- New user-facing behaviour ships with a test in `tests/`.

## The Minecraft mods

The economics are ported to a pure Java-8 `core` package shared by both loaders
(**Forge 1.8.9** in `mod/`, **Fabric 1.21.x** in `mod-fabric/`). The core has no
Minecraft or network dependencies, so it compiles and self-tests standalone:

```bash
OUT=$(mktemp -d)
javac --release 8 -d "$OUT" \
  $(find mod/src/main/java/com/nullifieduniverse/nulladdons/core -name '*.java') \
  mod/src/test/java/com/nullifieduniverse/nulladdons/core/FlipEngineSelfTest.java
java -cp "$OUT" com.nullifieduniverse.nulladdons.core.FlipEngineSelfTest
# -> "Null's Addons mod core: ALL 44 CHECKS PASSED"
```

Any change to the economics must keep the Python tests and the Java self-test in
agreement — they intentionally verify the same math. The Minecraft glue
(`client/`, `net/`, the Fabric loader) can only be built with the full Forge /
Loom toolchains, so keep all real logic in `core` where it's tested here.

## Pull requests

- Keep changes focused; describe *why*, not just *what*.
- Make sure `python3 -m unittest discover -s tests` and the Java self-test both
  pass. CI runs both.
- Add a line under `## [Unreleased]` in `CHANGELOG.md`.

Null's Addons is an unofficial, fan-made tool and is not affiliated with Hypixel
or Mojang.
