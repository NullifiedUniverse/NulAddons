package com.nullifieduniverse.nulladdons.fabric;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.nullifieduniverse.nulladdons.core.BazaarSnapshot;
import com.nullifieduniverse.nulladdons.core.CraftEngine;
import com.nullifieduniverse.nulladdons.core.CraftFlip;
import com.nullifieduniverse.nulladdons.core.EngineConfig;
import com.nullifieduniverse.nulladdons.core.Flip;
import com.nullifieduniverse.nulladdons.core.FlipEngine;
import com.nullifieduniverse.nulladdons.core.MayorEffect;
import com.nullifieduniverse.nulladdons.core.Product;
import com.nullifieduniverse.nulladdons.core.Recipe;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Modern async Bazaar + Mayor client using the JDK {@link HttpClient} (HTTP/2,
 * connection pooling). One low-priority daemon thread refreshes the Bazaar every
 * 60 s and the election every 10 min, precomputes ranked flips and craft flips,
 * and folds the Mayor's tax effect (e.g. Derpy = 0 % tax) into the economics.
 * The client thread only ever reads the {@code volatile} results.
 */
public final class BazaarClient {
    private static final String BAZAAR_URL = "https://api.hypixel.net/v2/skyblock/bazaar";
    private static final String ELECTION_URL = "https://api.hypixel.net/v2/resources/skyblock/election";

    private static final BazaarClient INSTANCE = new BazaarClient();
    public static BazaarClient get() { return INSTANCE; }

    private final HttpClient http = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(8)).build();
    private final AtomicReference<BazaarSnapshot> snapshot = new AtomicReference<BazaarSnapshot>();
    private final AtomicReference<List<Flip>> topFlips = new AtomicReference<List<Flip>>();
    private final AtomicReference<List<CraftFlip>> topCrafts = new AtomicReference<List<CraftFlip>>();
    private final AtomicReference<MayorEffect> mayor = new AtomicReference<MayorEffect>();
    private List<Recipe> recipes = java.util.Collections.emptyList();
    private ScheduledExecutorService scheduler;

    private BazaarClient() {}

    public void start() {
        if (scheduler != null) return;
        recipes = Recipes.loadBundled();
        scheduler = Executors.newSingleThreadScheduledExecutor(new ThreadFactory() {
            public Thread newThread(Runnable r) {
                Thread t = new Thread(r, "NullsAddons-Net");
                t.setDaemon(true);
                t.setPriority(Thread.MIN_PRIORITY);
                return t;
            }
        });
        scheduler.scheduleWithFixedDelay(this::safeRefreshElection, 0, 10, TimeUnit.MINUTES);
        scheduler.scheduleWithFixedDelay(this::safeRefreshBazaar, 1, 60, TimeUnit.SECONDS);
    }

    public void shutdown() {
        if (scheduler != null) scheduler.shutdownNow();
        scheduler = null;
    }

    public BazaarSnapshot getSnapshot() { return snapshot.get(); }
    public List<Flip> getTopFlips() { return topFlips.get(); }
    public List<CraftFlip> getTopCrafts() { return topCrafts.get(); }
    public MayorEffect getMayor() { return mayor.get(); }

    public Flip flipFor(String id) {
        BazaarSnapshot s = snapshot.get();
        return s == null ? null : FlipEngine.rawFlip(s.get(id), effectiveConfig());
    }

    public CraftFlip craftFor(String id) {
        return CraftEngine.forOutput(snapshot.get(), recipes, effectiveConfig(), id);
    }

    /** Recompute after a config toggle (cookie / conservative / mayor). */
    public void reapply() {
        recompute();
    }

    private EngineConfig effectiveConfig() {
        EngineConfig ec = NullsConfig.engineConfig();
        MayorEffect m = mayor.get();
        if (m != null) ec.tax *= m.taxMultiplier;
        return ec;
    }

    // --- background work ----------------------------------------------------

    private void safeRefreshBazaar() {
        long t0 = System.currentTimeMillis();
        try {
            BazaarSnapshot s = fetchBazaar();
            if (s != null && !s.isEmpty()) {
                snapshot.set(s);
                recompute();
                Telemetry.get().onFetch(System.currentTimeMillis() - t0, true);
            }
        } catch (Throwable t) {
            Telemetry.get().onFetch(System.currentTimeMillis() - t0, false);
        }
    }

    private void safeRefreshElection() {
        try {
            mayor.set(fetchMayor());
            recompute();
        } catch (Throwable ignored) {
        }
    }

    private void recompute() {
        BazaarSnapshot s = snapshot.get();
        if (s == null) return;
        EngineConfig ec = effectiveConfig();
        topFlips.set(FlipEngine.topFlips(s, ec, 10));
        topCrafts.set(CraftEngine.topCrafts(s, recipes, ec, 10));
    }

    private String getBody(String url) throws Exception {
        HttpRequest req = HttpRequest.newBuilder(URI.create(url))
                .header("User-Agent", "NullsAddons-Fabric/1.0")
                .timeout(Duration.ofSeconds(15)).GET().build();
        HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString());
        return resp.statusCode() == 200 ? resp.body() : null;
    }

    private BazaarSnapshot fetchBazaar() throws Exception {
        String body = getBody(BAZAAR_URL);
        if (body == null) return null;
        JsonObject root = JsonParser.parseString(body).getAsJsonObject();
        if (!root.has("products")) return null;
        long lastUpdated = root.has("lastUpdated") ? root.get("lastUpdated").getAsLong() : 0L;
        JsonObject products = root.getAsJsonObject("products");
        Map<String, Product> parsed = new HashMap<String, Product>(products.size() * 2);
        for (Map.Entry<String, JsonElement> e : products.entrySet()) {
            Product p = parseProduct(e.getKey(), e.getValue().getAsJsonObject());
            if (p != null) parsed.put(e.getKey(), p);
        }
        return new BazaarSnapshot(parsed, lastUpdated);
    }

    private MayorEffect fetchMayor() throws Exception {
        String body = getBody(ELECTION_URL);
        if (body == null) return null;
        JsonObject root = JsonParser.parseString(body).getAsJsonObject();
        JsonObject m = root.has("mayor") ? root.getAsJsonObject("mayor") : null;
        if (m == null) return null;
        String name = m.has("name") ? m.get("name").getAsString() : "";
        StringBuilder perks = new StringBuilder();
        if (m.has("perks")) {
            for (JsonElement pe : m.getAsJsonArray("perks")) {
                JsonObject po = pe.getAsJsonObject();
                if (po.has("name")) perks.append(po.get("name").getAsString()).append(' ');
                if (po.has("description")) perks.append(po.get("description").getAsString()).append(' ');
            }
        }
        return MayorEffect.detect(name, perks.toString());
    }

    private static Product parseProduct(String id, JsonObject blob) {
        try {
            JsonArray buy = blob.has("buy_summary") ? blob.getAsJsonArray("buy_summary") : null;
            JsonArray sell = blob.has("sell_summary") ? blob.getAsJsonArray("sell_summary") : null;
            if (buy == null || sell == null || buy.size() == 0 || sell.size() == 0) return null;
            double bestAsk = num(buy.get(0).getAsJsonObject(), "pricePerUnit");
            double bestBid = num(sell.get(0).getAsJsonObject(), "pricePerUnit");
            if (bestAsk <= 0 || bestBid <= 0) return null;
            JsonObject q = blob.has("quick_status") ? blob.getAsJsonObject("quick_status") : new JsonObject();
            return new Product(id, bestBid, bestAsk, lng(q, "buyMovingWeek"),
                    lng(q, "sellMovingWeek"), lng(q, "sellVolume"), lng(q, "buyVolume"));
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
