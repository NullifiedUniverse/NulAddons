#!/usr/bin/env bash
#
# Null's Addons — one-command mod build.
#
# Usage:   ./build.sh [all|fabric|forge]
#
# You do NOT need Gradle installed — each mod ships a Gradle wrapper that fetches
# the right version automatically. You DO need a JDK:
#   • Fabric (Minecraft 1.21) → JDK 21
#   • Forge  (Minecraft 1.8.9) → JDK 8
#
# Finished jars are copied into ./dist/ — drop the one for your Minecraft version
# into your `mods` folder.
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$ROOT/dist"

build() {
    local dir="$1" label="$2"
    if [ ! -x "$ROOT/$dir/gradlew" ]; then
        echo "✗ $ROOT/$dir/gradlew missing or not executable" >&2
        return 1
    fi
    echo "▶ Building $label  ($dir) …"
    ( cd "$ROOT/$dir" && ./gradlew --console=plain build )
    # Copy the real mod jar(s), skipping -sources / -dev / -slim variants.
    find "$ROOT/$dir/build/libs" -maxdepth 1 -name '*.jar' \
        ! -name '*-sources.jar' ! -name '*-dev.jar' ! -name '*-slim.jar' \
        -exec cp -v {} "$ROOT/dist/" \; 2>/dev/null || true
    echo "✓ $label built."
    echo
}

case "${1:-all}" in
    fabric) build mod-fabric "Fabric · Minecraft 1.21 (needs JDK 21)" ;;
    forge)  build mod        "Forge · Minecraft 1.8.9 (needs JDK 8)" ;;
    all)
        build mod-fabric "Fabric · Minecraft 1.21 (needs JDK 21)" || true
        build mod        "Forge · Minecraft 1.8.9 (needs JDK 8)"   || true
        ;;
    *) echo "usage: ./build.sh [all|fabric|forge]" >&2; exit 1 ;;
esac

echo "Done. Jars are in:  $ROOT/dist/"
echo "Copy the one matching your Minecraft version into your 'mods' folder. gg."
