# Null's Addons — Minecraft Mod (Hypixel SkyBlock)

The in‑game half of Null's Addons: a **client‑side Forge 1.8.9 mod** that brings
the Bazaar‑flipping engine right into Hypixel SkyBlock, styled to sit seamlessly
next to SkyBlockAddons / NEU / Skytils.

It does two things, and only when you need them:

* **Top‑flips HUD** — a small, movable panel listing the best flips right now
  (`Enchanted Mithril  +15.1%  11.7M/hr`). Toggle it with **N**. It renders
  *only* while you're actually playing on SkyBlock. The panel fades in when it
  appears and its header gently pulses while a genuinely *cracked* flip is on the
  board — a nudge you can't miss, drawn with the pure, unit‑tested `core/Anim`.
* **Bazaar tooltips** — hover any Bazaar‑tradable item in a SkyBlock menu and its
  live **buy‑order / sell‑offer / margin / coins‑per‑hour** appear under the lore,
  in native SkyBlock styling. Identity comes from the item's own
  `ExtraAttributes.id`, so it's exact; non‑Bazaar items are left untouched.

## Built for zero performance impact

This was the hard requirement, and it's baked into the architecture:

* **All work is off‑thread.** A single low‑priority daemon thread fetches the
  public Bazaar endpoint every **60 s** and precomputes the ranked flips
  (`net/BazaarClient`). The render and tooltip code never touch the network or do
  the heavy math — they only read two `volatile` references.
* **Nothing runs when you don't need it.** Every render handler returns on the
  first cheap check unless you're on SkyBlock with the feature enabled; the
  SkyBlock check itself is cached for a second. In menus, other games, or
  singleplayer the mod is effectively idle.
* **Cheap draw path.** The HUD is one translucent rectangle plus a few
  precomputed strings — no per‑frame allocation or network.
* **Fail‑safe.** A transient network/JSON error is swallowed; one malformed or
  newly‑added Bazaar product is skipped, never fatal.

## The engine is the same one, ported and tested

`src/main/java/.../core/` is pure Java (no Minecraft, no network): the faithful
port of the Python engine — bid‑ask spread, 0.1 undercut, 1.25 % sell tax (1.1 %
with a Booster Cookie), congestion‑aware fill time, coins/hour, and the
manipulation guards (liquidity floor, spread‑outlier and absurd‑margin ceilings)
that stop it ever recommending fake profit. It ships with a self‑test:

```bash
# from mod/ — verifies the ported economics (JDK 8+)
javac --release 8 -d build/selftest \
  src/main/java/com/nullifieduniverse/nulladdons/core/*.java \
  src/test/java/com/nullifieduniverse/nulladdons/core/FlipEngineSelfTest.java
java -cp build/selftest com.nullifieduniverse.nulladdons.core.FlipEngineSelfTest
# -> Null's Addons mod core: ALL 20 CHECKS PASSED
```

## Build & install

**Requirements:** Minecraft **1.8.9** with **Minecraft Forge**, and to build,
**JDK 8** + **Gradle 4.x** (ForgeGradle 2.1 targets 1.8.9).

```bash
cd mod
gradle build          # or: ./gradlew build  (after `gradle wrapper` once)
# jar appears in build/libs/NullsAddons-1.8.9-1.0.0.jar
```

Copy that jar into your `.minecraft/mods/` folder (the 1.8.9 Forge profile) and
launch. That's it.

## Using it

* Join Hypixel and enter SkyBlock — the HUD appears (top‑left by default).
* Press **N** to show/hide the HUD.
* Open the **Bazaar** and hover items to see their flip numbers inline.
* Configure via **Mods → Null's Addons → Config**, or edit
  `.minecraft/config/nulladdons.cfg`:
  * `hudEnabled`, `tooltipEnabled`, `hudX`, `hudY`, `hudCount`
  * `cookieActive` (Booster Cookie → lower tax), `conservative` (only deep,
    stable, near‑risk‑free flips).

## Notes

* **Client‑side and advisory.** It reads the public Bazaar API and shows you
  information; it never automates play or interacts with the server on your
  behalf — the same philosophy as the CLI tool.
* **Aesthetic.** All text uses SkyBlock `§` colour codes and coin abbreviations
  (k/M/B) so it blends in with the game and the mods you already run.
* Want a Fabric / modern‑version port? The `core/` package is engine‑only and
  portable — only the thin `client/` + `net/` glue is Forge‑specific.
