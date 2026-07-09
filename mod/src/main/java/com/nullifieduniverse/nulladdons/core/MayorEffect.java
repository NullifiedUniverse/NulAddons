package com.nullifieduniverse.nulladdons.core;

import java.util.Locale;

/**
 * The SkyBlock Mayor's effect on the Bazaar economy (new capability), ported
 * from the Python engine. Pure detection from the mayor name + perk text so it's
 * unit-tested; the Fabric layer fetches the election and applies the result.
 *
 * <ul>
 *   <li><b>Derpy</b> ("Tax Evasion") -> tax multiplier 0 (no Bazaar/AH tax).</li>
 *   <li><b>Mining / Farming / Fishing</b> mayors -> supply-glut notes.</li>
 * </ul>
 */
public final class MayorEffect {
    public final String mayor;
    public final double taxMultiplier;
    public final String note;
    public final String tag;

    private MayorEffect(String mayor, double taxMultiplier, String note, String tag) {
        this.mayor = mayor;
        this.taxMultiplier = taxMultiplier;
        this.note = note;
        this.tag = tag;
    }

    public boolean taxFree() { return taxMultiplier <= 1e-6; }

    public static MayorEffect detect(String mayorName, String perkText) {
        String name = mayorName == null ? "" : mayorName;
        String text = (name + " " + (perkText == null ? "" : perkText)).toLowerCase(Locale.US);
        if (text.contains("tax evasion") || text.contains("derpy")) {
            return new MayorEffect(name, 0.0,
                    "TAX-FREE — 0% Bazaar tax! Flip big.", "tax_free");
        }
        if (contains(text, "mining fiesta", "molten forge", "prospection", "cole")) {
            return new MayorEffect(name, 1.0,
                    "Mining mayor: ore supply up, prices soften.", "mining");
        }
        if (contains(text, "farming", "blooming business", "pelt", "finnegan")) {
            return new MayorEffect(name, 1.0,
                    "Farming mayor: crop supply up, prices soften.", "farming");
        }
        if (contains(text, "fishing festival", "marina")) {
            return new MayorEffect(name, 1.0,
                    "Fishing mayor: sea-creature supply up.", "fishing");
        }
        return new MayorEffect(name, 1.0, "", "none");
    }

    private static boolean contains(String haystack, String... needles) {
        for (String n : needles) if (haystack.contains(n)) return true;
        return false;
    }
}
