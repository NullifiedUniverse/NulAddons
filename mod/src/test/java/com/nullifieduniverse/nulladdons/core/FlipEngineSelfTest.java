package com.nullifieduniverse.nulladdons.core;

import com.nullifieduniverse.nulladdons.core.telemetry.TelemetryBuffer;
import com.nullifieduniverse.nulladdons.core.telemetry.TelemetryEvent;

import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Standalone self-test for the pure economics core (no Minecraft, no network).
 * Compile with {@code javac --release 8} and run to verify the port matches the
 * Python engine. Not shipped in the mod jar (lives under src/test).
 */
public final class FlipEngineSelfTest {
    private static int checks = 0;

    private static void check(boolean cond, String msg) {
        checks++;
        if (!cond) throw new AssertionError("FAILED: " + msg);
    }

    private static void near(double a, double b, String msg) {
        check(Math.abs(a - b) < 1e-3, msg + " (got " + a + ", want " + b + ")");
    }

    public static void main(String[] args) {
        EngineConfig cfg = new EngineConfig();

        // 1) Core flip economics match flip_unit_economics(100, 110, 0.0125).
        Product x = new Product("X", 100, 110, 10_000_000L, 10_000_000L, 1000L, 1000L);
        Flip f = FlipEngine.evaluate(x, cfg);
        check(f != null, "healthy flip should evaluate");
        near(f.buyOrder, 100.1, "buy order = bid + 0.1");
        near(f.sellOffer, 109.9, "sell offer = ask - 0.1");
        near(f.unitProfit, 109.9 * 0.9875 - 100.1, "unit profit after tax");
        near(f.margin, (109.9 * 0.9875 - 100.1) / 100.1, "margin");
        check(f.coinsPerHour > 0, "coins/hour positive");
        check(f.confidence > 0 && f.confidence <= 1.0, "confidence in (0,1]");

        // 2) A book too tight to squeeze between is rejected.
        check(FlipEngine.evaluate(new Product("T", 100, 100.1, 10_000_000L,
                10_000_000L, 1000L, 1000L), cfg) == null, "tight book -> null");

        // 3) Spread-outlier guard (manipulation): huge spread% is skipped.
        check(FlipEngine.evaluate(new Product("Z", 1, 100000, 10_000_000L,
                10_000_000L, 1000L, 1000L), cfg) == null, "spread outlier -> null");

        // 4) Absurd-margin ceiling (raise the spread guard so margin is the gate).
        EngineConfig wide = new EngineConfig();
        wide.maxSpreadPct = 2.0;
        check(FlipEngine.evaluate(new Product("M", 100, 500, 10_000_000L,
                10_000_000L, 1000L, 1000L), wide) == null,
                "absurd margin (>maxMargin) -> null");

        // 5) Congestion fades capture.
        Product calm = new Product("C1", 100, 110, 10_000_000L, 10_000_000L, 1000L, 1000L);
        Product busy = new Product("C2", 100, 110, 10_000_000L, 10_000_000L,
                100_000_000L, 1000L);
        double cc = FlipEngine.effectiveCapture(calm, 0.5, true);
        double cb = FlipEngine.effectiveCapture(busy, 0.5, true);
        check(cb < cc && cb > 0, "congested book -> lower capture");
        check(cc <= 0.5, "capture never exceeds base");

        // 6) Cookie lowers the tax => a slightly better margin on the same book.
        EngineConfig cookie = new EngineConfig();
        cookie.setCookie(true);
        Flip fc = FlipEngine.evaluate(x, cookie);
        check(fc != null && fc.margin > f.margin, "cookie tax improves margin");

        // 7) Formatting is SkyBlock-shaped.
        check(Format.coins(1_234_567).equals("1.23M"), "coins 1.23M");
        check(Format.coins(50_000_000).equals("50.00M"), "coins 50.00M");
        check(Format.coins(2_000_000_000L).equals("2.00B"), "coins 2.00B");
        check(Format.niceName("ENCHANTED_DIAMOND_BLOCK").equals("Enchanted Diamond Block"),
                "nice name");
        check(Format.niceName("INK_SACK:4").equals("Ink Sack"), "nice name strips legacy id");
        check(Format.pct(0.151).equals("+15.1%"), "pct format");

        // 8) topFlips ranks and filters.
        Map<String, Product> m = new HashMap<String, Product>();
        Product good = new Product("GOOD", 100, 110, 10_000_000L, 10_000_000L, 1000L, 1000L);
        Product bad = new Product("BAD", 100, 100.1, 10_000_000L, 10_000_000L, 1000L, 1000L);
        m.put(good.productId, good);
        m.put(bad.productId, bad);
        List<Flip> top = FlipEngine.topFlips(new BazaarSnapshot(m, 0L), cfg, 10);
        check(top.size() == 1 && top.get(0).productId.equals("GOOD"),
                "topFlips keeps only the good one");

        // 9) Craft-flip: buy raws, craft, sell the enchanted output.
        Map<String, Product> cm = new HashMap<String, Product>();
        cm.put("RAW", new Product("RAW", 5, 6, 10_000_000L, 10_000_000L, 1000L, 1000L));
        cm.put("ENCH", new Product("ENCH", 1000, 1100, 10_000_000L, 10_000_000L, 1000L, 1000L));
        BazaarSnapshot cs = new BazaarSnapshot(cm, 0L);
        Recipe rec = new Recipe("ENCH", 1, Arrays.asList(new Recipe.Ingredient("RAW", 160)));
        CraftFlip cf = CraftEngine.evaluate(cs, rec, cfg);
        check(cf != null, "craft flip should evaluate");
        near(cf.costPerOutput, 160 * 5.1, "craft cost = 160 * (bid + 0.1)");
        near(cf.margin, (1099.9 * 0.9875 - 816.0) / 816.0, "craft margin");
        check(CraftEngine.forOutput(cs, Arrays.asList(rec), cfg, "ENCH") != null,
                "forOutput finds the recipe");
        check(CraftEngine.forOutput(cs, Arrays.asList(rec), cfg, "NOPE") == null,
                "forOutput unknown -> null");
        // Absurd craft margin is rejected by the ceiling.
        Map<String, Product> am = new HashMap<String, Product>();
        am.put("RAW", cm.get("RAW"));
        am.put("ENCH2", new Product("ENCH2", 100000, 101000, 10_000_000L, 10_000_000L, 1000L, 1000L));
        check(CraftEngine.evaluate(new BazaarSnapshot(am, 0L),
                new Recipe("ENCH2", 1, Arrays.asList(new Recipe.Ingredient("RAW", 160))), cfg) == null,
                "absurd craft margin -> null");

        // 10) Mayor effect detection.
        MayorEffect derpy = MayorEffect.detect("Derpy", "Tax Evasion: no tax.");
        check(derpy.taxFree() && derpy.taxMultiplier == 0.0, "Derpy is tax-free");
        MayorEffect diana = MayorEffect.detect("Diana", "Huntress' Intuition");
        check(!diana.taxFree() && diana.taxMultiplier == 1.0, "Diana no tax effect");
        check(MayorEffect.detect("Cole", "Mining Fiesta").tag.equals("mining"),
                "Cole tagged mining");

        // 11a) Bounded: a cap-2 buffer drops the oldest event.
        TelemetryBuffer bounded = new TelemetryBuffer(2);
        bounded.add(new TelemetryEvent("first"));
        bounded.add(new TelemetryEvent("second"));
        bounded.add(new TelemetryEvent("third"));
        check(bounded.size() == 2, "buffer bounded to capacity");
        check(!bounded.drainToJson("x", "1", "1").contains("first"), "oldest event dropped");

        // 11b) JSON is well-formed, PII-free and escaped.
        TelemetryBuffer buf = new TelemetryBuffer(10);
        buf.add(new TelemetryEvent("hud_shown").put("count", 5).put("enabled", true));
        buf.add(new TelemetryEvent("quote\"name"));
        String json = buf.drainToJson("anon-123", "1.0.0", "1.21");
        check(json.contains("\"anon_id\":\"anon-123\""), "payload has anon id");
        check(json.contains("\"mc\":\"1.21\""), "payload has mc version");
        check(json.contains("\"count\":5"), "numeric field emitted raw (no quotes)");
        check(json.contains("\"enabled\":true"), "boolean field emitted raw");
        check(json.contains("quote\\\"name"), "string values are JSON-escaped");
        check(buf.isEmpty(), "buffer drains empty");
        check(TelemetryBuffer.escape("a\"b\\c").equals("a\\\"b\\\\c"), "escape quotes/backslashes");

        System.out.println("Null's Addons mod core: ALL " + checks + " CHECKS PASSED");
    }
}
