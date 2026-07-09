package com.nullifieduniverse.nulladdons.fabric;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.context.CommandContext;
import net.fabricmc.fabric.api.client.command.v2.ClientCommandManager;
import net.fabricmc.fabric.api.client.command.v2.FabricClientCommandSource;
import net.minecraft.command.CommandRegistryAccess;
import net.minecraft.text.Text;

/** Client commands: {@code /nulladdons hud | craft | telemetry ... | feedback}. */
public final class Commands {
    private Commands() {}

    public static void register(CommandDispatcher<FabricClientCommandSource> dispatcher,
                                CommandRegistryAccess access) {
        dispatcher.register(ClientCommandManager.literal("nulladdons")
                .executes(c -> {
                    msg(c, "§7/nulladdons hud | craft | telemetry on|off|status | feedback <msg>");
                    return 1;
                })
                .then(ClientCommandManager.literal("hud").executes(c -> {
                    NullsConfig.hudEnabled = !NullsConfig.hudEnabled;
                    NullsConfig.save();
                    msg(c, "HUD " + (NullsConfig.hudEnabled ? "§ashown" : "§chidden"));
                    return 1;
                }))
                .then(ClientCommandManager.literal("craft").executes(c -> {
                    NullsConfig.showCraft = !NullsConfig.showCraft;
                    NullsConfig.save();
                    BazaarClient.get().reapply();
                    msg(c, "Craft tooltips " + (NullsConfig.showCraft ? "§aon" : "§coff"));
                    return 1;
                }))
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
                            msg(c, "Telemetry: " + (NullsConfig.telemetryEnabled ? "§aon" : "§coff")
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

    private static boolean endpointSet() {
        return NullsConfig.telemetryEndpoint != null
                && !NullsConfig.telemetryEndpoint.trim().isEmpty();
    }

    private static String shortId() {
        String id = NullsConfig.anonId == null ? "" : NullsConfig.anonId;
        return id.length() >= 8 ? id.substring(0, 8) + "…" : id;
    }

    private static void msg(CommandContext<FabricClientCommandSource> c, String s) {
        c.getSource().sendFeedback(Text.literal("§6[Null's Addons] §r" + s));
    }
}
