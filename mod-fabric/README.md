# Null's Addons — Fabric Mod (modern Minecraft, 1.21+)

The modern build of the in‑game companion: a **Fabric** client mod for
**Minecraft 1.21.x** (Java 21). Same Bazaar‑flipping engine as the Forge 1.8.9
build — in fact the exact same `core` package, reused with zero duplication — but
on the current toolchain, with new capabilities and optional telemetry.

## Features

* **Top‑flips HUD** (toggle **N**, or `/nulladdons hud`) — movable panel, renders
  only in‑world on SkyBlock.
* **Item tooltips** — hover any Bazaar‑tradable item in a SkyBlock menu to see its
  live **buy‑order / sell‑offer / margin / coins‑per‑hour**, read from the item's
  own `custom_data → ExtraAttributes.id`.
* **Craft flips** (new) — tooltips also show craft‑from‑mats profit for enchanted
  items (`Craft from mats: +41.4%`). Toggle with `/nulladdons craft`.
* **Mayor‑aware economics** (new) — the mod reads the live election; under
  **Derpy** ("Tax Evasion") the Bazaar tax drops to 0 % and every margin
  recalculates. Mining/Farming/Fishing mayors are recognised too.
* **Optional telemetry & feedback** — opt‑in, off by default; see
  [TELEMETRY.md](TELEMETRY.md).

## Zero performance impact (same as the 1.8.9 build)

* One low‑priority daemon thread (`BazaarClient`) refreshes the Bazaar every 60 s
  and the election every 10 min using the JDK `HttpClient`, and precomputes
  ranked flips/crafts. The client thread only reads `volatile` results.
* Every render/tooltip handler returns on the first cheap check unless you're on
  SkyBlock with the feature enabled (SkyBlock detection cached 1 s). Idle
  everywhere else.
* Draw path is one `fill` + a few precomputed strings; parsing is fail‑safe.

## Shared, tested engine

`src/main/java/.../core/**` is **not duplicated** — `build.gradle` adds the Forge
project's `core` package as a source directory (excluding its Forge glue), so both
mods compile the identical, unit‑tested economics (order flips, craft flips,
mayor effect, tax/undercut/confidence, manipulation guards, telemetry buffer).
Verify it (JDK 8+):

```bash
cd ../mod
javac --release 8 -d build/selftest \
  src/main/java/com/nullifieduniverse/nulladdons/core/*.java \
  src/main/java/com/nullifieduniverse/nulladdons/core/telemetry/*.java \
  src/test/java/com/nullifieduniverse/nulladdons/core/FlipEngineSelfTest.java
java -cp build/selftest com.nullifieduniverse.nulladdons.core.FlipEngineSelfTest
# -> Null's Addons mod core: ALL 38 CHECKS PASSED
```

## Build & install

**Requirements:** JDK 21, and Fabric Loader + **Fabric API** in your 1.21.x
profile.

```bash
cd mod-fabric
gradle build          # or ./gradlew build after `gradle wrapper`
# jar -> build/libs/nulladdons-fabric-1.0.0.jar
```

Drop the jar (and Fabric API) into `.minecraft/mods/`. Launch the 1.21.x Fabric
profile, join Hypixel, and enter SkyBlock.

Version strings live in `gradle.properties` (`minecraft_version`,
`yarn_mappings`, `loader_version`, `fabric_version`) — bump them to retarget a
newer Minecraft; the code doesn't change. The glue targets the 1.21.4 Fabric/Yarn
API surface (e.g. component `custom_data`, `HudRenderCallback(DrawContext,
RenderTickCounter)`); a different 1.21.x point release may need a mapping/name
tweak in the thin `fabric/` layer only — the `core` engine is unaffected.

## Commands

```
/nulladdons hud                 toggle the HUD
/nulladdons craft               toggle craft-flip tooltips
/nulladdons telemetry on|off|status
/nulladdons feedback <message>  send feedback (see TELEMETRY.md)
```
