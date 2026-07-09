package com.nullifieduniverse.nulladdons.core;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;

/**
 * Craft-flip economics (new capability): buy the materials on the Bazaar with
 * buy orders, craft, and sell the output — capturing the enchant/compact
 * value-add. Single-step per recipe (buy the listed inputs), which stays exact
 * and shares the same tax, undercut, confidence and manipulation guards as the
 * order-flip engine. Pure Java 8, unit-tested.
 */
public final class CraftEngine {
    private CraftEngine() {}

    static double flowPerMin(long weekly) {
        return (double) weekly / EngineConfig.WEEK_MINUTES;
    }

    public static CraftFlip evaluate(BazaarSnapshot snap, Recipe r, EngineConfig cfg) {
        if (snap == null || r == null) return null;
        Product out = snap.get(r.output);
        if (out == null || !out.hasTwoSidedMarket()) return null;
        if (out.demandPerWeek < cfg.minLiquidity) return null;
        if (out.spreadPct() > cfg.maxSpreadPct) return null;

        double cost = 0.0;
        double buyRate = Double.POSITIVE_INFINITY;   // slowest input = binding
        for (Recipe.Ingredient in : r.inputs) {
            Product ip = snap.get(in.id);
            if (ip == null || ip.bestBid <= 0) return null;   // can't price a mat
            double unitBuy = ip.bestBid + EngineConfig.UNDERCUT_INCREMENT;
            cost += unitBuy * in.count;
            double rate = flowPerMin(ip.supplyPerWeek)
                    * FlipEngine.effectiveCapture(ip, cfg.captureFraction, true)
                    / Math.max(1, in.count);
            if (rate < buyRate) buyRate = rate;
        }
        cost /= r.outputQty;
        if (cost <= 0) return null;

        double sellOffer = out.bestAsk - EngineConfig.UNDERCUT_INCREMENT;
        double revenue = sellOffer * (1.0 - cfg.tax);
        double unitProfit = revenue - cost;
        double margin = unitProfit / cost;
        if (unitProfit < cfg.minUnitProfit) return null;
        if (margin < cfg.minMargin || margin > cfg.maxMargin) return null;

        double sellRate = flowPerMin(out.demandPerWeek)
                * FlipEngine.effectiveCapture(out, cfg.captureFraction, false);
        double coinsPerHour = 0.0;
        if (sellRate > 0 && buyRate > 0 && buyRate != Double.POSITIVE_INFINITY) {
            double minutesPerOutput = (1.0 / buyRate) + (1.0 / sellRate);
            coinsPerHour = unitProfit * 60.0 / minutesPerOutput;
        }
        if (coinsPerHour < cfg.minCoinsPerHour) return null;

        return new CraftFlip(r.output, cost, sellOffer, unitProfit, margin,
                coinsPerHour, FlipEngine.confidence(out, margin));
    }

    /** Craft flip for a specific output id (for Bazaar tooltips), or null. */
    public static CraftFlip forOutput(BazaarSnapshot snap, List<Recipe> recipes,
                                      EngineConfig cfg, String outputId) {
        if (recipes == null || outputId == null) return null;
        for (Recipe r : recipes) {
            if (outputId.equals(r.output)) return evaluate(snap, r, cfg);
        }
        return null;
    }

    public static List<CraftFlip> topCrafts(BazaarSnapshot snap, List<Recipe> recipes,
                                            EngineConfig cfg, int limit) {
        List<CraftFlip> flips = new ArrayList<CraftFlip>();
        if (recipes != null) {
            for (Recipe r : recipes) {
                CraftFlip c = evaluate(snap, r, cfg);
                if (c != null) flips.add(c);
            }
        }
        Collections.sort(flips, new Comparator<CraftFlip>() {
            public int compare(CraftFlip a, CraftFlip b) {
                return Double.compare(b.score(), a.score());
            }
        });
        if (limit > 0 && flips.size() > limit) {
            return new ArrayList<CraftFlip>(flips.subList(0, limit));
        }
        return flips;
    }
}
