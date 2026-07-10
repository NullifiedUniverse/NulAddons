package com.nullifieduniverse.nulladdons.core;

/**
 * Tiny, pure-math animation helpers for the HUD (fade-in, a gentle pulse for a
 * cracked flip, ARGB alpha scaling). No Minecraft, no mutable state — the loader
 * feeds in a timestamp and gets back a number — so it's unit-tested in the core
 * self-test and shared by both the Forge and Fabric HUDs. Like the rest of the
 * core it is pure presentation: it never touches a price or a margin.
 */
public final class Anim {
    private Anim() {}

    /** Clamp to the unit interval. */
    public static double clamp01(double v) {
        return v < 0.0 ? 0.0 : (v > 1.0 ? 1.0 : v);
    }

    /** Ease-out cubic on {@code t} in [0,1]: quick start, gentle settle. */
    public static double easeOutCubic(double t) {
        double inv = 1.0 - clamp01(t);
        return 1.0 - inv * inv * inv;
    }

    /**
     * Fade-in alpha in [0,1] for something first shown {@code elapsedMs} ago over
     * a {@code durationMs} window. Clamps, so it stays at 1 once the fade is done.
     */
    public static double fadeAlpha(long elapsedMs, long durationMs) {
        if (durationMs <= 0L) return 1.0;
        return easeOutCubic((double) elapsedMs / (double) durationMs);
    }

    /**
     * A smooth 0→1→0 pulse (raised cosine) with the given period in ms — for a
     * subtle "this one's spicy" shimmer on a cracked flip. Starts at 0.
     */
    public static double pulse(long timeMs, double periodMs) {
        if (periodMs <= 0.0) return 1.0;
        double phase = Math.floorMod(timeMs, (long) periodMs) / periodMs;  // 0..1
        return 0.5 - 0.5 * Math.cos(phase * 2.0 * Math.PI);
    }

    /** Scale the alpha channel of an ARGB colour by {@code a} in [0,1]. */
    public static int withAlpha(int argb, double a) {
        int base = (argb >>> 24) & 0xFF;
        int alpha = (int) Math.round(base * clamp01(a));
        return (alpha << 24) | (argb & 0x00FFFFFF);
    }

    /** Linear blend of two values, {@code t} in [0,1]. */
    public static double lerp(double from, double to, double t) {
        return from + (to - from) * clamp01(t);
    }
}
