# Building the Null's Addons mod

There are three ways to get the mod jar, easiest first.

## 0. Don't build it — download it 🏆

Every tagged release attaches prebuilt jars, and the **Build Mods** GitHub
Action uploads them as artifacts on demand. Grab the jar that matches your
Minecraft version, drop it in your `mods` folder, done. No JDK, no Gradle, no
terminal.

- Releases: the **Assets** of the latest release.
- Latest from any commit: **Actions → Build Mods → (latest run) → Artifacts**.

## 1. One command 🛠️

You do **not** need Gradle installed — each mod ships a Gradle *wrapper* that
downloads the correct Gradle version itself. You only need a **JDK**:

| Mod | Minecraft | JDK |
|---|---|---|
| Fabric (`mod-fabric/`) | 1.21.x | **21** |
| Forge (`mod/`) | 1.8.9 | **8** |

```bash
./build.sh            # both mods  (Windows: build.bat)
./build.sh fabric     # just the modern one
./build.sh forge      # just the 1.8.9 one
./build.sh run        # launch the Fabric dev client to try it live
```

Jars land in `./dist/`. Copy the one for your version into your Minecraft
`mods` folder.

### 🍎 macOS

`build.sh` is macOS‑aware: it finds the right JDK for each mod automatically via
`/usr/libexec/java_home`, so you can have both installed and never think about it.

```bash
# install the JDKs once (Homebrew):
brew install --cask temurin@21     # Fabric (1.21)
brew install --cask temurin@8      # Forge  (1.8.9)

./build.sh fabric      # picks temurin@21 for you
./build.sh forge       # picks temurin@8 for you
./build.sh run         # launch the Fabric dev client (Minecraft 1.21)
```

- To force a specific JDK, set `JAVA21_HOME` / `JAVA8_HOME` before running.
- `./build.sh run` launches a throwaway dev client; Fabric Loom adds the macOS
  `-XstartOnFirstThread` flag for you, so it opens cleanly on Apple Silicon and
  Intel alike.
- To actually play: install **Fabric Loader for 1.21** (or Forge 1.8.9) with the
  official installer, then drop the jar from `./dist/` into
  `~/Library/Application Support/minecraft/mods`.
- The **Fabric** build is the smooth one on Apple Silicon. The **Forge 1.8.9**
  toolchain predates arm64 — if `./build.sh forge` struggles, use an x86 JDK 8
  (`brew install --cask temurin@8` provides one that runs under Rosetta) or just
  grab the prebuilt Forge jar from CI (option 0 above).

## 2. Straight Gradle 🔧

```bash
cd mod-fabric && ./gradlew build     # Fabric 1.21  → build/libs/*.jar   (JDK 21)
cd mod        && ./gradlew build     # Forge 1.8.9  → build/libs/*.jar   (JDK 8)
```

On Windows use `gradlew.bat` instead of `./gradlew`.

### Picking the JDK

If you have several JDKs installed, point Gradle at the right one for that mod:

```bash
./gradlew build -Dorg.gradle.java.home="/path/to/jdk-21"   # Fabric
./gradlew build -Dorg.gradle.java.home="/path/to/jdk-8"    # Forge
```

`temurin` builds from [Adoptium](https://adoptium.net/) work great for both.

## Notes

- **First build is slow** — Gradle downloads itself, then the Minecraft/Fabric
  (or Forge) toolchain. Later builds are cached and fast.
- The two mods share one tested economics core (`mod/…/core/`); the Fabric build
  reuses it directly, so a change to the math lands in both.
- Want to verify the core logic without a full mod build? It's pure Java 8:
  ```bash
  javac --release 8 -d out \
    $(find mod/src/main/java/com/nullifieduniverse/nulladdons/core -name '*.java') \
    mod/src/test/java/com/nullifieduniverse/nulladdons/core/FlipEngineSelfTest.java
  java -cp out com.nullifieduniverse.nulladdons.core.FlipEngineSelfTest
  ```
