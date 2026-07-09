package com.nullifieduniverse.nulladdons.fabric;

import net.minecraft.client.MinecraftClient;
import net.minecraft.client.network.ServerInfo;
import net.minecraft.scoreboard.Scoreboard;
import net.minecraft.scoreboard.ScoreboardDisplaySlot;
import net.minecraft.scoreboard.ScoreboardObjective;

import java.util.Locale;

/** Cheap, cached "am I on Hypixel SkyBlock?" check so nothing renders elsewhere. */
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
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc == null || mc.world == null || mc.player == null) return false;
        ServerInfo server = mc.getCurrentServerEntry();
        if (server == null || server.address == null
                || !server.address.toLowerCase(Locale.ROOT).contains("hypixel")) {
            return false;
        }
        Scoreboard sb = mc.world.getScoreboard();
        ScoreboardObjective obj = sb.getObjectiveForSlot(ScoreboardDisplaySlot.SIDEBAR);
        if (obj == null) return false;
        String title = obj.getDisplayName().getString();
        return title != null && title.toUpperCase(Locale.ROOT).contains("SKYBLOCK");
    }
}
