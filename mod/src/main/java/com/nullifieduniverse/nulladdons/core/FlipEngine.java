package com.nullifieduniverse.nulladdons.core;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;

/**
 * The economics core, ported faithfully from the Python engine:
 * bid-ask spread, undercut queue priority, 1.25% sell tax, congestion-aware
 * fill time, coins/hour, and the manipulation guards (liquidity floor, spread
 * outlier and absurd-margin ceilings) that stop it recommending fake profit.
 *
 * <p>Pure and deterministic — no Minecraft, no network — so it is unit-tested
 * directly (see {@code FlipEngineSelfTest}).
 */
public final class FlipEngine {
    private FlipEngine() {}

    // Confidence curve anchors (mirror the Python constants).
    private static final double LIQ_FLOOR = 50_000.0;
    private static final double LIQ_FULL = 10_000_000.0;
    private static final double SUSPICIOUS_MARGIN = 0.50;

    private static double flowPerMin(long weekly) {
        return (double) weekly / EngineConfig.WEEK_MINUTES;
    }

    /** Fade capture when the same-side book is congested (undercut-war risk). */
    static double effectiveCapture(Product p, double base, boolean buySide) {
        long resting = buySide ? p.bidVolume : p.askVolume;
        long weeklyFlow = buySide ? p.supplyPerWeek : p.demandPerWeek;
        double dailyFlow = weeklyFlow / 7.0;
        if (dailyFlow <= 0) return 0.0;
        double backlogDays = resting / dailyFlow;
        return base / (1.0 + 0.5 * backlogDays);
    }

    private static double clamp01(double x) {
        return Math.max(0.0, Math.min(1.0, x));
    }

    private static double liquidityConfidence(long liquidity) {
        if (liquidity <= LIQ_FLOOR) return 0.0;
        double span = Math.log10(LIQ_FULL) - Math.log10(LIQ_FLOOR);
        return clamp01((Math.log10(liquidity) - Math.log10(LIQ_FLOOR)) / span);
    }

    private static double marginConfidence(double margin) {
        if (margin <= 0) return 0.0;
        if (margin <= 0.15) return clamp01(0.4 + margin / 0.15 * 0.6);
        if (margin <= SUSPICIOUS_MARGIN) return 1.0;
        return clamp01(1.0 - (margin - SUSPICIOUS_MARGIN) * 1.5); // huge => suspicious
    }

    static double confidence(Product p, double margin) {
        double liq = liquidityConfidence(p.liquidity());
        double spread = clamp01(1.0 - p.spreadPct() / 0.5);
        double marg = marginConfidence(margin);
        return clamp01(0.50 * liq + 0.25 * marg + 0.25 * spread);
    }

    /** Evaluate one product; returns a sized-agnostic {@link Flip} or null. */
    public static Flip evaluate(Product p, EngineConfig cfg) {
        if (p == null || !p.hasTwoSidedMarket()) return null;
        if (p.liquidity() < cfg.minLiquidity) return null;
        if (p.spreadPct() > cfg.maxSpreadPct) return null;

        double buyOrder = p.bestBid + EngineConfig.UNDERCUT_INCREMENT;
        double sellOffer = p.bestAsk - EngineConfig.UNDERCUT_INCREMENT;
        double revenue = sellOffer * (1.0 - cfg.tax);
        double unitProfit = revenue - buyOrder;
        double margin = buyOrder > 0 ? unitProfit / buyOrder : 0.0;

        if (unitProfit < cfg.minUnitProfit) return null;
        if (margin < cfg.minMargin || margin > cfg.maxMargin) return null;

        double supplyRate = flowPerMin(p.supplyPerWeek) * effectiveCapture(p, cfg.captureFraction, true);
        double demandRate = flowPerMin(p.demandPerWeek) * effectiveCapture(p, cfg.captureFraction, false);
        if (supplyRate <= 0 || demandRate <= 0) return null;

        // coins/hour is a rate independent of quantity (profit & time both scale).
        double minutesPerUnit = (1.0 / supplyRate) + (1.0 / demandRate);
        double coinsPerHour = unitProfit * 60.0 / minutesPerUnit;
        if (coinsPerHour < cfg.minCoinsPerHour) return null;

        return new Flip(p.productId, buyOrder, sellOffer, unitProfit, margin,
                coinsPerHour, confidence(p, margin));
    }

    /**
     * Compute a flip's numbers for a single product WITHOUT the qualifying
     * filters — used to annotate whatever item the player hovers in the Bazaar,
     * even a thin one. Returns null only if there's no two-sided market.
     */
    public static Flip rawFlip(Product p, EngineConfig cfg) {
        if (p == null || !p.hasTwoSidedMarket()) return null;
        double buyOrder = p.bestBid + EngineConfig.UNDERCUT_INCREMENT;
        double sellOffer = p.bestAsk - EngineConfig.UNDERCUT_INCREMENT;
        double unitProfit = sellOffer * (1.0 - cfg.tax) - buyOrder;
        double margin = buyOrder > 0 ? unitProfit / buyOrder : 0.0;
        double supplyRate = flowPerMin(p.supplyPerWeek) * effectiveCapture(p, cfg.captureFraction, true);
        double demandRate = flowPerMin(p.demandPerWeek) * effectiveCapture(p, cfg.captureFraction, false);
        double coinsPerHour = 0.0;
        if (supplyRate > 0 && demandRate > 0 && unitProfit > 0) {
            coinsPerHour = unitProfit * 60.0 / ((1.0 / supplyRate) + (1.0 / demandRate));
        }
        return new Flip(p.productId, buyOrder, sellOffer, unitProfit, margin,
                coinsPerHour, confidence(p, margin));
    }

    /** All qualifying flips, best risk-adjusted opportunity first. */
    public static List<Flip> topFlips(BazaarSnapshot snapshot, EngineConfig cfg, int limit) {
        List<Flip> flips = new ArrayList<Flip>();
        if (snapshot == null) return flips;
        for (Product p : snapshot.products.values()) {
            Flip f = evaluate(p, cfg);
            if (f != null) flips.add(f);
        }
        Collections.sort(flips, new Comparator<Flip>() {
            public int compare(Flip a, Flip b) {
                return Double.compare(b.score(), a.score());
            }
        });
        if (limit > 0 && flips.size() > limit) {
            return new ArrayList<Flip>(flips.subList(0, limit));
        }
        return flips;
    }
}
