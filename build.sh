#!/usr/bin/env bash
#
# Null's Addons — one-command mod build (macOS / Linux).
#
# Usage:
#   ./build.sh [all|fabric|forge]   build the mod jar(s) into ./dist/
#   ./build.sh run                  launch the Fabric dev client (Minecraft 1.21)
#
# You do NOT need Gradle installed — each mod ships a Gradle wrapper that fetches
# the right version itself. You DO need a JDK per mod:
#   • Fabric (Minecraft 1.21) → JDK 21
#   • Forge  (Minecraft 1.8.9) → JDK 8
#
# On macOS this script finds the matching JDK for you via /usr/libexec/java_home,
# so you can have both installed and it picks the right one automatically. Point
# it explicitly with JAVA8_HOME / JAVA21_HOME if you want.
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$ROOT/dist"

is_macos() { [ "$(uname)" = "Darwin" ]; }

# Echo the JAVA_HOME to use for a given major version, or "" if none found.
pick_jdk() {
    major="$1"
    home=""
    case "$major" in
        8)  home="${JAVA8_HOME:-}"  ;;
        21) home="${JAVA21_HOME:-}" ;;
    esac
    if [ -z "$home" ] && is_macos && [ -x /usr/libexec/java_home ]; then
        home="$(/usr/libexec/java_home -v "$major" 2>/dev/null || true)"
    fi
    printf '%s' "$home"
}

jdk_hint() {
    major="$1"
    echo "  ! Couldn't find a JDK $major — using whatever 'java' is on your PATH." >&2
    if is_macos; then
        echo "    Install it:   brew install --cask temurin@$major" >&2
        echo "    ...or set JAVA${major}_HOME to a JDK $major." >&2
    else
        echo "    Install a JDK $major (e.g. Adoptium Temurin) or set JAVA${major}_HOME." >&2
    fi
}

# gradle_in <dir> <jdk-major> <task...>
gradle_in() {
    dir="$1"; major="$2"; shift 2
    jh="$(pick_jdk "$major")"
    [ -z "$jh" ] && jdk_hint "$major"
    if [ ! -x "$ROOT/$dir/gradlew" ]; then
        echo "  ✗ $ROOT/$dir/gradlew missing or not executable" >&2
        return 1
    fi
    echo "▶ ($dir) gradle $*  ${jh:+[JDK: $jh]}"
    if [ -n "$jh" ]; then
        ( cd "$ROOT/$dir" && ./gradlew "-Dorg.gradle.java.home=$jh" --console=plain "$@" )
    else
        ( cd "$ROOT/$dir" && ./gradlew --console=plain "$@" )
    fi
}

build() {
    dir="$1"; major="$2"; label="$3"
    echo "── Building $label ──"
    gradle_in "$dir" "$major" build
    find "$ROOT/$dir/build/libs" -maxdepth 1 -name '*.jar' \
        ! -name '*-sources.jar' ! -name '*-dev.jar' ! -name '*-slim.jar' \
        -exec cp -v {} "$ROOT/dist/" \; 2>/dev/null || true
    echo "✓ $label built."; echo
}

case "${1:-all}" in
    fabric) build mod-fabric 21 "Fabric · Minecraft 1.21 (JDK 21)" ;;
    forge)  build mod         8 "Forge · Minecraft 1.8.9 (JDK 8)" ;;
    all)
        build mod-fabric 21 "Fabric · Minecraft 1.21 (JDK 21)" || true
        build mod         8 "Forge · Minecraft 1.8.9 (JDK 8)"   || true
        ;;
    run)
        # Loom adds -XstartOnFirstThread on macOS automatically, so the dev
        # client launches cleanly on Apple Silicon and Intel alike.
        echo "── Launching Fabric dev client (Minecraft 1.21) ──"
        gradle_in mod-fabric 21 runClient
        exit 0
        ;;
    *) echo "usage: ./build.sh [all|fabric|forge|run]" >&2; exit 1 ;;
esac

echo "Done. Jars are in:  $ROOT/dist/"
echo "Copy the one matching your Minecraft version into your 'mods' folder. gg."
