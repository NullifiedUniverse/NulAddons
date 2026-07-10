package com.nullifieduniverse.nulladdons.fabric;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.context.CommandContext;
import net.fabricmc.fabric.api.client.command.v2.ClientCommandManager;
import net.fabricmc.fabric.api.client.command.v2.FabricClientCommandSource;
import net.minecraft.command.CommandRegistryAccess;
import net.minecraft.text.Text;

/**
 * Client commands under {@code /nulladdons}. Type {@code /nulladdons help} for the
 * full list. Everything here is display/opt-in only — no command touches the game
 * or automates play.
 */
public final class Commands {
    private Commands() {}

    public static void register(CommandDispatcher<FabricClientCommandSource> dispatcher,
                                CommandRegistryAccess access) {
        dispatcher.register(ClientCommandManager.literal("nulladdons")
                .executes(c -> { help(c); return 1; })

                .then(ClientCommandManager.literal("help").executes(c -> { help(c); return 1; }))

                .then(ClientCommandManager.literal("hud").executes(c -> {
                    NullsConfig.hudEnabled = !NullsConfig.hudEnabled;
                    NullsConfig.save();
                    msg(c, "HUD " + onOff(NullsConfig.hudEnabled));
                    return 1;
                }))

                .then(ClientCommandManager.literal("tooltip").executes(c -> {
                    NullsConfig.tooltipEnabled = !NullsConfig.tooltipEnabled;
                    NullsConfig.save();
                    msg(c, "Bazaar tooltips " + onOff(NullsConfig.tooltipEnabled));
                    return 1;
                }))

                .then(ClientCommandManager.literal("craft").executes(c -> {
                    NullsConfig.showCraft = !NullsConfig.showCraft;
                    NullsConfig.save();
                    BazaarClient.get().reapply();
                    msg(c, "Craft tooltips " + onOff(NullsConfig.showCraft));
                    return 1;
                }))

                .then(ClientCommandManager.literal("count")
                        .then(ClientCommandManager.argument("n", IntegerArgumentType.integer(1, 10))
                                .executes(c -> {
                                    NullsConfig.hudCount = IntegerArgumentType.getInteger(c, "n");
                                    NullsConfig.save();
                                    msg(c, "HUD now shows §f" + NullsConfig.hudCount + "§7 flip(s).");
                                    return 1;
                                })))

                .then(ClientCommandManager.literal("move")
                        .then(ClientCommandManager.argument("x", IntegerArgumentType.integer(0))
                                .then(ClientCommandManager.argument("y", IntegerArgumentType.integer(0))
                                        .executes(c -> {
                                            NullsConfig.hudX = IntegerArgumentType.getInteger(c, "x");
                                            NullsConfig.hudY = IntegerArgumentType.getInteger(c, "y");
                                            NullsConfig.save();
                                            msg(c, "HUD moved to §f" + NullsConfig.hudX + ", "
                                                    + NullsConfig.hudY + "§7.");
                                            return 1;
                                        }))))

                .then(ClientCommandManager.literal("telemetry")
                        .then(ClientCommandManager.literal("on").executes(c -> {
                            NullsConfig.telemetryEnabled = true;
                            NullsConfig.save();
                            msg(c, "§aTelemetry ON §7— anonymous usage stats only. "
                                    + "Turn off any time with §f/nulladdons telemetry off§7.");
                            if (!endpointSet()) {
                                msg(c, "§eNote: no telemetryEndpoint set in config, so nothing "
                                        + "is actually sent yet.");
                            }
                            return 1;
                        }))
                        .then(ClientCommandManager.literal("off").executes(c -> {
                            NullsConfig.telemetryEnabled = false;
                            NullsConfig.save();
                            msg(c, "§cTelemetry OFF.");
                            return 1;
                        }))
                        .then(ClientCommandManager.literal("status").executes(c -> {
                            msg(c, "Telemetry: " + onOff(NullsConfig.telemetryEnabled)
                                    + "§7 · endpoint " + (endpointSet() ? "§aset" : "§cnot set")
                                    + "§7 · anon id " + shortId());
                            return 1;
                        })))

                .then(ClientCommandManager.literal("feedback")
                        .then(ClientCommandManager.argument("message", StringArgumentType.greedyString())
                                .executes(c -> {
                                    String m = StringArgumentType.getString(c, "message");
                                    boolean sent = Telemetry.get().feedback(m);
                                    msg(c, sent ? "§aThanks — feedback sent!"
                                            : "§cSet 'telemetryEndpoint' in config/nulladdons.json first.");
                                    return 1;
                                }))));
    }

    private static void help(CommandContext<FabricClientCommandSource> c) {
        msg(c, "§lcommands §r§7(you can also press §fN§7 to toggle the HUD)");
        line(c, "help", "this list");
        line(c, "hud", "show/hide the top-flips panel");
        line(c, "tooltip", "toggle flip numbers on Bazaar item tooltips");
        line(c, "craft", "toggle craft-from-mats numbers in tooltips");
        line(c, "count <1-10>", "how many flips the HUD shows");
        line(c, "move <x> <y>", "reposition the HUD panel");
        line(c, "telemetry on|off|status", "opt-in local stats (off by default)");
        line(c, "feedback <message>", "send a quick note to the devs");
        msg(c, "§8config/nulladdons.json · advisory only — it never plays for you");
    }

    private static String onOff(boolean b) {
        return b ? "§ashown" : "§chidden";
    }

    private static boolean endpointSet() {
        return NullsConfig.telemetryEndpoint != null
                && !NullsConfig.telemetryEndpoint.trim().isEmpty();
    }

    private static String shortId() {
        String id = NullsConfig.anonId == null ? "" : NullsConfig.anonId;
        return id.length() >= 8 ? id.substring(0, 8) + "…" : id;
    }

    private static void line(CommandContext<FabricClientCommandSource> c, String cmd, String desc) {
        c.getSource().sendFeedback(Text.literal("  §e/nulladdons " + cmd + " §8— §7" + desc));
    }

    private static void msg(CommandContext<FabricClientCommandSource> c, String s) {
        c.getSource().sendFeedback(Text.literal("§6[Null's Addons] §r" + s));
    }
}
