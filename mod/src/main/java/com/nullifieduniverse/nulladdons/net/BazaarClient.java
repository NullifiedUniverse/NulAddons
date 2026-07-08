package com.nullifieduniverse.nulladdons.net;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.nullifieduniverse.nulladdons.core.BazaarSnapshot;
import com.nullifieduniverse.nulladdons.core.EngineConfig;
import com.nullifieduniverse.nulladdons.core.Flip;
import com.nullifieduniverse.nulladdons.core.FlipEngine;
import com.nullifieduniverse.nulladdons.core.Product;

import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Fetches the public Bazaar endpoint on a single background thread and caches
 * the parsed snapshot plus a precomputed top-flips list.
 *
 * <p><b>Performance is the whole design:</b> the network call and the flip
 * computation happen off the game thread on a 60-second schedule; the render and
 * tooltip code only ever read two {@code volatile} references, so there is zero
 * per-frame work and zero network on the client thread. When the player isn't on
 * SkyBlock the mod simply doesn't read these, and the timer is cheap.
 */
public final class BazaarClient {
    private static final String URL_STR = "https://api.hypixel.net/v2/skyblock/bazaar";
    private static final int REFRESH_SECONDS = 60;

    private static final BazaarClient INSTANCE = new BazaarClient();
    public static BazaarClient get() { return INSTANCE; }

    private final AtomicReference<BazaarSnapshot> snapshot = new AtomicReference<BazaarSnapshot>();
    private final AtomicReference<List<Flip>> topFlips = new AtomicReference<List<Flip>>();
    private volatile EngineConfig config = new EngineConfig();
    private ScheduledExecutorService scheduler;

    private BazaarClient() {}

    public void start() {
        if (scheduler != null) return;
        scheduler = Executors.newSingleThreadScheduledExecutor(new java.util.concurrent.ThreadFactory() {
            public Thread newThread(Runnable r) {
                Thread t = new Thread(r, "NullsAddons-Bazaar");
                t.setDaemon(true);        // never keep the JVM alive
                t.setPriority(Thread.MIN_PRIORITY);
                return t;
            }
        });
        scheduler.scheduleWithFixedDelay(new Runnable() {
            public void run() { safeRefresh(); }
        }, 0, REFRESH_SECONDS, TimeUnit.SECONDS);
    }

    public void shutdown() {
        if (scheduler != null) scheduler.shutdownNow();
        scheduler = null;
    }

    public void setConfig(EngineConfig cfg) {
        this.config = cfg;
        recomputeFlips();  // reflect new thresholds without waiting for a refresh
    }

    public BazaarSnapshot getSnapshot() { return snapshot.get(); }
    public List<Flip> getTopFlips() { return topFlips.get(); }

    /** On-demand flip numbers for one product (for Bazaar tooltips). */
    public Flip flipFor(String productId) {
        BazaarSnapshot s = snapshot.get();
        if (s == null || productId == null) return null;
        return FlipEngine.rawFlip(s.get(productId), config);
    }

    // --- background work ----------------------------------------------------

    private void safeRefresh() {
        try {
            BazaarSnapshot s = fetch();
            if (s != null && !s.isEmpty()) {
                snapshot.set(s);
                recomputeFlips();
            }
        } catch (Throwable ignored) {
            // Never let a transient network/JSON error crash the timer.
        }
    }

    private void recomputeFlips() {
        BazaarSnapshot s = snapshot.get();
        if (s != null) topFlips.set(FlipEngine.topFlips(s, config, 10));
    }

    private BazaarSnapshot fetch() throws Exception {
        HttpURLConnection conn = (HttpURLConnection) new URL(URL_STR).openConnection();
        conn.setRequestMethod("GET");
        conn.setConnectTimeout(8000);
        conn.setReadTimeout(15000);
        conn.setRequestProperty("User-Agent", "NullsAddons-Mod/1.0");
        try {
            if (conn.getResponseCode() != 200) return null;
            JsonObject root;
            InputStreamReader reader = new InputStreamReader(conn.getInputStream(),
                    StandardCharsets.UTF_8);
            try {
                root = new JsonParser().parse(reader).getAsJsonObject();
            } finally {
                reader.close();
            }
            if (!root.has("products")) return null;
            long lastUpdated = root.has("lastUpdated") ? root.get("lastUpdated").getAsLong() : 0L;
            JsonObject products = root.getAsJsonObject("products");
            Map<String, Product> parsed = new HashMap<String, Product>(products.size() * 2);
            for (Map.Entry<String, com.google.gson.JsonElement> e : products.entrySet()) {
                Product p = parseProduct(e.getKey(), e.getValue().getAsJsonObject());
                if (p != null) parsed.put(e.getKey(), p);
            }
            return new BazaarSnapshot(parsed, lastUpdated);
        } finally {
            conn.disconnect();
        }
    }

    /** Defensive parse: a single malformed/new product is skipped, not fatal. */
    private static Product parseProduct(String id, JsonObject blob) {
        try {
            JsonArray buy = blob.has("buy_summary") ? blob.getAsJsonArray("buy_summary") : null;   // asks
            JsonArray sell = blob.has("sell_summary") ? blob.getAsJsonArray("sell_summary") : null; // bids
            if (buy == null || sell == null || buy.size() == 0 || sell.size() == 0) return null;
            double bestAsk = num(buy.get(0).getAsJsonObject(), "pricePerUnit");
            double bestBid = num(sell.get(0).getAsJsonObject(), "pricePerUnit");
            if (bestAsk <= 0 || bestBid <= 0) return null;
            JsonObject q = blob.has("quick_status") ? blob.getAsJsonObject("quick_status") : new JsonObject();
            long demand = lng(q, "buyMovingWeek");
            long supply = lng(q, "sellMovingWeek");
            long askVol = lng(q, "buyVolume");
            long bidVol = lng(q, "sellVolume");
            return new Product(id, bestBid, bestAsk, demand, supply, bidVol, askVol);
        } catch (Throwable t) {
            return null;
        }
    }

    private static double num(JsonObject o, String k) {
        try { return o.has(k) && !o.get(k).isJsonNull() ? o.get(k).getAsDouble() : 0.0; }
        catch (Throwable t) { return 0.0; }
    }

    private static long lng(JsonObject o, String k) {
        try { return o.has(k) && !o.get(k).isJsonNull() ? o.get(k).getAsLong() : 0L; }
        catch (Throwable t) { return 0L; }
    }
}
