package com.nullifieduniverse.nulladdons.core;

/**
 * Tunable knobs for the flip engine — the Java mirror of the Python
 * {@code EvalParams} + risk profiles. Mutated live from the mod's config screen.
 */
public final class EngineConfig {
    // Game mechanics
    public static final double UNDERCUT_INCREMENT = 0.1;
    public static final int WEEK_MINUTES = 7 * 24 * 60; // 10,080
    public static final double BASE_TAX = 0.0125;       // 1.25%
    public static final double COOKIE_TAX = 0.011;      // 1.10% with a Booster Cookie

    // Effective tax (base, lowered by cookie / raised by 0 under Derpy — future).
    public double tax = BASE_TAX;

    // Risk / filtering
    public double captureFraction = 0.5;   // share of instant-flow your front order wins
    public long minLiquidity = 400_000;    // weekly-flow floor
    public double minMargin = 0.02;        // 2% after-tax
    public double maxMargin = 3.0;         // absurd-margin ceiling (manipulation guard)
    public double maxSpreadPct = 0.50;     // spread-outlier guard
    public double minUnitProfit = 0.2;     // ignore dust
    public double minCoinsPerHour = 0.0;

    public EngineConfig() {}

    public void setCookie(boolean active) {
        this.tax = active ? COOKIE_TAX : BASE_TAX;
    }

    /** Strict, near-risk-free preset (the "conservative"/guaranteed profile). */
    public EngineConfig conservative() {
        captureFraction = 0.35;
        minLiquidity = 1_000_000;
        minMargin = 0.03;
        maxMargin = 1.5;
        maxSpreadPct = 0.25;
        minUnitProfit = 0.5;
        minCoinsPerHour = 50_000;
        return this;
    }
}
