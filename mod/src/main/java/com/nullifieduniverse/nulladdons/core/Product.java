package com.nullifieduniverse.nulladdons.core;

/**
 * One Bazaar product with disambiguated market fields.
 *
 * <p>The Hypixel API's own naming is famously reversed, so we translate it once
 * here (as in the Python tool): {@code buy_summary} is actually the sell offers
 * you buy <em>from</em> (asks) and {@code sell_summary} the buy orders you sell
 * <em>to</em> (bids). Everything downstream uses the unambiguous names below.
 *
 * <p>Pure data — no Minecraft or JSON dependencies — so the whole economics core
 * compiles and unit-tests on its own.
 */
public final class Product {
    public final String productId;
    public final double bestBid;        // highest buy order  (you sell to this)
    public final double bestAsk;        // lowest sell offer  (you buy from this)
    public final long demandPerWeek;    // buyMovingWeek  -> feeds YOUR sell offers
    public final long supplyPerWeek;    // sellMovingWeek -> feeds YOUR buy orders
    public final long bidVolume;        // resting buy-order units
    public final long askVolume;        // resting sell-offer units

    public Product(String productId, double bestBid, double bestAsk,
                   long demandPerWeek, long supplyPerWeek,
                   long bidVolume, long askVolume) {
        this.productId = productId;
        this.bestBid = bestBid;
        this.bestAsk = bestAsk;
        this.demandPerWeek = demandPerWeek;
        this.supplyPerWeek = supplyPerWeek;
        this.bidVolume = bidVolume;
        this.askVolume = askVolume;
    }

    public boolean hasTwoSidedMarket() {
        return bestBid > 0 && bestAsk > 0 && bestAsk > bestBid;
    }

    public double spread() {
        return bestAsk - bestBid;
    }

    public double mid() {
        return (bestAsk + bestBid) / 2.0;
    }

    public double spreadPct() {
        double m = mid();
        return m > 0 ? spread() / m : 0.0;
    }

    /** Conservative liquidity = the thinner of the two weekly flows. */
    public long liquidity() {
        return Math.min(demandPerWeek, supplyPerWeek);
    }
}
