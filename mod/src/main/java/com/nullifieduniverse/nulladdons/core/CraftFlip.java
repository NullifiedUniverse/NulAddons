package com.nullifieduniverse.nulladdons.core;

/** A computed craft-flip: buy the mats on Bazaar, craft, sell the output. */
public final class CraftFlip {
    public final String outputId;
    public final double costPerOutput;   // buy-order cost of the inputs, per output
    public final double sellOffer;       // price to list the output at
    public final double unitProfit;      // coins/output after tax
    public final double margin;
    public final double coinsPerHour;
    public final double confidence;

    public CraftFlip(String outputId, double costPerOutput, double sellOffer,
                     double unitProfit, double margin, double coinsPerHour,
                     double confidence) {
        this.outputId = outputId;
        this.costPerOutput = costPerOutput;
        this.sellOffer = sellOffer;
        this.unitProfit = unitProfit;
        this.margin = margin;
        this.coinsPerHour = coinsPerHour;
        this.confidence = confidence;
    }

    public double score() { return coinsPerHour * confidence; }
}
