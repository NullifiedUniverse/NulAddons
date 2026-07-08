package com.nullifieduniverse.nulladdons.core;

import java.util.Collections;
import java.util.Map;

/** An immutable in-memory view of the Bazaar: {@code productId -> Product}. */
public final class BazaarSnapshot {
    public final Map<String, Product> products;
    public final long lastUpdated;   // epoch millis from the API
    public final long fetchedAt;     // epoch millis when we received it

    public BazaarSnapshot(Map<String, Product> products, long lastUpdated) {
        this.products = Collections.unmodifiableMap(products);
        this.lastUpdated = lastUpdated;
        this.fetchedAt = System.currentTimeMillis();
    }

    public Product get(String productId) {
        return products.get(productId);
    }

    public boolean isEmpty() {
        return products.isEmpty();
    }

    public long ageSeconds() {
        return Math.max(0L, (System.currentTimeMillis() - fetchedAt) / 1000L);
    }
}
