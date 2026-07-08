package com.nullifieduniverse.nulladdons.client;

import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ServerData;
import net.minecraft.scoreboard.ScoreObjective;
import net.minecraft.scoreboard.Scoreboard;
import net.minecraft.util.StringUtils;

/**
 * Cheap detection of "am I on Hypixel SkyBlock right now?" so the mod only ever
 * renders where it belongs. Cached for a second to avoid re-reading the
 * scoreboard every frame — one of several small choices that keep the render
 * path free.
 */
public final class SkyblockState {
    private SkyblockState() {}

    private static boolean cached;
    private static long cachedAt;

    public static boolean onSkyblock() {
        long now = System.currentTimeMillis();
        if (now - cachedAt < 1000L) return cached;
        cachedAt = now;
        cached = compute();
        return cached;
    }

    private static boolean compute() {
        Minecraft mc = Minecraft.getMinecraft();
        if (mc == null || mc.theWorld == null || mc.thePlayer == null) return false;
        if (mc.isSingleplayer()) return false;
        ServerData server = mc.getCurrentServerData();
        if (server == null || server.serverIP == null
                || !server.serverIP.toLowerCase().contains("hypixel")) {
            return false;
        }
        Scoreboard sb = mc.theWorld.getScoreboard();
        if (sb == null) return false;
        ScoreObjective sidebar = sb.getObjectiveInDisplaySlot(1); // 1 = sidebar
        if (sidebar == null) return false;
        String title = StringUtils.stripControlCodes(sidebar.getDisplayName());
        return title != null && title.toUpperCase().contains("SKYBLOCK");
    }
}
