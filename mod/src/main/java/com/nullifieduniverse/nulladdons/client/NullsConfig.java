package com.nullifieduniverse.nulladdons.client;

import com.nullifieduniverse.nulladdons.NullsAddonsMod;
import com.nullifieduniverse.nulladdons.core.EngineConfig;
import com.nullifieduniverse.nulladdons.net.BazaarClient;
import net.minecraftforge.common.config.Configuration;
import net.minecraftforge.fml.client.event.ConfigChangedEvent;
import net.minecraftforge.fml.common.eventhandler.SubscribeEvent;

import java.io.File;

/** Persistent settings, editable from the Mods-menu config screen or by keybind. */
public final class NullsConfig {
    private static final String GENERAL = "general";
    private static Configuration config;

    // Display
    public static boolean hudEnabled = true;
    public static boolean tooltipEnabled = true;
    public static int hudX = 3;
    public static int hudY = 3;
    public static int hudCount = 3;

    // Economics
    public static boolean cookieActive = false;   // Booster Cookie -> lower tax
    public static boolean conservative = false;   // strict, near-risk-free filters

    public static void init(File file) {
        config = new Configuration(file);
        load();
    }

    public static Configuration getConfig() {
        return config;
    }

    public static void load() {
        if (config == null) return;
        config.load();
        hudEnabled = config.getBoolean("hudEnabled", GENERAL, true,
                "Show the top-flips HUD panel on SkyBlock");
        tooltipEnabled = config.getBoolean("tooltipEnabled", GENERAL, true,
                "Add flip info to Bazaar item tooltips");
        hudX = config.getInt("hudX", GENERAL, 3, 0, 10000, "HUD x position");
        hudY = config.getInt("hudY", GENERAL, 3, 0, 10000, "HUD y position");
        hudCount = config.getInt("hudCount", GENERAL, 3, 1, 10, "How many flips to show");
        cookieActive = config.getBoolean("cookieActive", GENERAL, false,
                "Booster Cookie active (lowers Bazaar tax 1.25% -> 1.1%)");
        conservative = config.getBoolean("conservative", GENERAL, false,
                "Only surface deep, stable, near-risk-free flips");
        if (config.hasChanged()) config.save();
    }

    /** Persist runtime changes (e.g. the HUD toggle keybind). */
    public static void save() {
        if (config == null) return;
        config.get(GENERAL, "hudEnabled", true).set(hudEnabled);
        config.get(GENERAL, "tooltipEnabled", true).set(tooltipEnabled);
        config.get(GENERAL, "hudX", 3).set(hudX);
        config.get(GENERAL, "hudY", 3).set(hudY);
        config.get(GENERAL, "hudCount", 3).set(hudCount);
        config.get(GENERAL, "cookieActive", false).set(cookieActive);
        config.get(GENERAL, "conservative", false).set(conservative);
        config.save();
    }

    public static EngineConfig engineConfig() {
        EngineConfig ec = new EngineConfig();
        if (conservative) ec.conservative();
        ec.setCookie(cookieActive);
        return ec;
    }

    @SubscribeEvent
    public void onConfigChanged(ConfigChangedEvent.OnConfigChangedEvent event) {
        if (NullsAddonsMod.MODID.equals(event.modID)) {
            load();
            BazaarClient.get().setConfig(engineConfig());
        }
    }
}
