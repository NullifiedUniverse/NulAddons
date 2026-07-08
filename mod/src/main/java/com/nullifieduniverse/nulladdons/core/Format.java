package com.nullifieduniverse.nulladdons.core;

import java.util.Locale;

/**
 * SkyBlock-style formatting: coin abbreviations (k/M/B) and pretty item names,
 * plus the § colour codes so the mod's text sits seamlessly next to vanilla and
 * other SkyBlock mods. Pure string helpers (no Minecraft classes).
 */
public final class Format {
    private Format() {}

    public static final char SECT = '§'; // §

    public static String coins(double n) {
        String sign = n < 0 ? "-" : "";
        double a = Math.abs(n);
        if (a >= 1_000_000_000.0) return sign + trim(a / 1_000_000_000.0) + "B";
        if (a >= 1_000_000.0) return sign + trim(a / 1_000_000.0) + "M";
        if (a >= 1_000.0) return sign + trim(a / 1_000.0) + "k";
        return sign + String.format(Locale.US, "%.1f", a);
    }

    private static String trim(double v) {
        return String.format(Locale.US, "%.2f", v);
    }

    /** Price with thousands separators, one decimal (as typed into the Bazaar). */
    public static String price(double n) {
        return String.format(Locale.US, "%,.1f", n);
    }

    public static String pct(double frac) {
        return String.format(Locale.US, "%+.1f%%", frac * 100.0);
    }

    /** "ENCHANTED_DIAMOND_BLOCK" / "INK_SACK:4" -> "Enchanted Diamond Block". */
    public static String niceName(String productId) {
        String base = productId;
        int colon = base.indexOf(':');
        if (colon >= 0) base = base.substring(0, colon);
        String[] parts = base.toLowerCase(Locale.US).split("_");
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < parts.length; i++) {
            if (parts[i].isEmpty()) continue;
            if (sb.length() > 0) sb.append(' ');
            sb.append(Character.toUpperCase(parts[i].charAt(0)));
            if (parts[i].length() > 1) sb.append(parts[i].substring(1));
        }
        return sb.length() > 0 ? sb.toString() : productId;
    }

    /** A green/yellow/red colour code by how healthy a margin is. */
    public static String marginColor(double margin) {
        if (margin >= 0.08) return SECT + "a";  // green
        if (margin >= 0.03) return SECT + "e";  // yellow
        return SECT + "6";                       // gold
    }
}
