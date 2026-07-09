package com.nullifieduniverse.nulladdons.core;

import java.util.Random;

/**
 * The mod's personality — taglines and a "cracked flip" hype label — kept out of
 * the numbers. Toggleable: {@link #setSerious(boolean)} (wired to a config flag)
 * returns clean, neutral output for anyone who wants a boring HUD. Pure Java 8,
 * unit-tested; never affects prices or margins.
 */
public final class Flair {
    private Flair() {}

    private static boolean serious = false;

    public static void setSerious(boolean value) { serious = value; }
    public static boolean isSerious() { return serious; }

    private static final String[] TAGLINES = {
            "flip coins, not tables",
            "buy low, sell slightly-less-low",
            "the bazaar doesn't care about your feelings",
            "number go up (most of the time)",
            "not financial advice, it's SkyBlock",
            "we undercut by 0.1 and we're not sorry",
    };

    /** A daily-rotating tagline (empty in serious mode). */
    public static String tagline() {
        return tagline(System.currentTimeMillis() / 86_400_000L);
    }

    public static String tagline(long seed) {
        if (serious || TAGLINES.length == 0) return "";
        return TAGLINES[(int) (Math.floorMod(new Random(seed).nextInt(), TAGLINES.length))];
    }

    /**
     * A hype label for how juicy a margin is, using § colours so it sits in the
     * HUD/tooltip. Empty for normal margins (and always empty in serious mode).
     */
    public static String crackedLabel(double margin) {
        if (serious) return "";
        if (margin >= 0.25) return "§d§lCRACKED";
        if (margin >= 0.12) return "§6HOT";
        return "";
    }
}
