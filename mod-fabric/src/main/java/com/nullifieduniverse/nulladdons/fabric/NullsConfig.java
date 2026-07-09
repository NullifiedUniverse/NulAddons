package com.nullifieduniverse.nulladdons.fabric;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.nullifieduniverse.nulladdons.core.EngineConfig;
import net.fabricmc.loader.api.FabricLoader;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.UUID;

/** JSON config at {@code config/nulladdons.json}. Dependency-light (gson only). */
public final class NullsConfig {
    private static final Path PATH =
            FabricLoader.getInstance().getConfigDir().resolve("nulladdons.json");
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

    // Display
    public static boolean hudEnabled = true;
    public static boolean tooltipEnabled = true;
    public static boolean showCraft = true;
    public static int hudX = 4;
    public static int hudY = 4;
    public static int hudCount = 3;

    // Economics
    public static boolean cookieActive = false;
    public static boolean conservative = false;

    // Telemetry — opt-in, OFF by default, no endpoint until you set one.
    public static boolean telemetryEnabled = false;
    public static String telemetryEndpoint = "";
    public static String anonId = "";

    private NullsConfig() {}

    public static void load() {
        try {
            if (Files.exists(PATH)) {
                JsonObject o = JsonParser.parseString(
                        new String(Files.readAllBytes(PATH), StandardCharsets.UTF_8))
                        .getAsJsonObject();
                hudEnabled = bool(o, "hudEnabled", hudEnabled);
                tooltipEnabled = bool(o, "tooltipEnabled", tooltipEnabled);
                showCraft = bool(o, "showCraft", showCraft);
                hudX = intv(o, "hudX", hudX);
                hudY = intv(o, "hudY", hudY);
                hudCount = intv(o, "hudCount", hudCount);
                cookieActive = bool(o, "cookieActive", cookieActive);
                conservative = bool(o, "conservative", conservative);
                telemetryEnabled = bool(o, "telemetryEnabled", telemetryEnabled);
                telemetryEndpoint = str(o, "telemetryEndpoint", telemetryEndpoint);
                anonId = str(o, "anonId", anonId);
            }
        } catch (Exception ignored) {
            // Corrupt config -> keep defaults, rewrite a clean one below.
        }
        if (anonId == null || anonId.isEmpty()) {
            anonId = UUID.randomUUID().toString();   // anonymous install id, not the account
        }
        save();
    }

    public static void save() {
        try {
            JsonObject o = new JsonObject();
            o.addProperty("hudEnabled", hudEnabled);
            o.addProperty("tooltipEnabled", tooltipEnabled);
            o.addProperty("showCraft", showCraft);
            o.addProperty("hudX", hudX);
            o.addProperty("hudY", hudY);
            o.addProperty("hudCount", hudCount);
            o.addProperty("cookieActive", cookieActive);
            o.addProperty("conservative", conservative);
            o.addProperty("telemetryEnabled", telemetryEnabled);
            o.addProperty("telemetryEndpoint", telemetryEndpoint);
            o.addProperty("anonId", anonId);
            Files.createDirectories(PATH.getParent());
            Files.write(PATH, GSON.toJson(o).getBytes(StandardCharsets.UTF_8));
        } catch (Exception ignored) {
        }
    }

    public static EngineConfig engineConfig() {
        EngineConfig ec = new EngineConfig();
        if (conservative) ec.conservative();
        ec.setCookie(cookieActive);
        return ec;
    }

    private static boolean bool(JsonObject o, String k, boolean d) {
        return o.has(k) && !o.get(k).isJsonNull() ? o.get(k).getAsBoolean() : d;
    }

    private static int intv(JsonObject o, String k, int d) {
        try { return o.has(k) && !o.get(k).isJsonNull() ? o.get(k).getAsInt() : d; }
        catch (Exception e) { return d; }
    }

    private static String str(JsonObject o, String k, String d) {
        return o.has(k) && !o.get(k).isJsonNull() ? o.get(k).getAsString() : d;
    }
}
