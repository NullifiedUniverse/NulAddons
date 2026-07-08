package com.nullifieduniverse.nulladdons.core;

/** A single, computed order-flip opportunity (immutable result). */
public final class Flip {
    public final String productId;
    public final double buyOrder;      // price to type into a Buy Order
    public final double sellOffer;     // price to type into a Sell Offer
    public final double unitProfit;    // coins/unit after tax
    public final double margin;        // unitProfit / buyOrder
    public final double coinsPerHour;  // velocity-adjusted (qty-independent rate)
    public final double confidence;    // 0..1

    public Flip(String productId, double buyOrder, double sellOffer,
                double unitProfit, double margin, double coinsPerHour,
                double confidence) {
        this.productId = productId;
        this.buyOrder = buyOrder;
        this.sellOffer = sellOffer;
        this.unitProfit = unitProfit;
        this.margin = margin;
        this.coinsPerHour = coinsPerHour;
        this.confidence = confidence;
    }

    /** Risk-adjusted ranking key: velocity discounted by confidence. */
    public double score() {
        return coinsPerHour * confidence;
    }
}
