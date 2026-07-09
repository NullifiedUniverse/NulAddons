package com.nullifieduniverse.nulladdons.fabric;

import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.command.v2.ClientCommandRegistrationCallback;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientLifecycleEvents;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.item.v1.ItemTooltipCallback;
import net.fabricmc.fabric.api.client.rendering.v1.HudRenderCallback;

/**
 * Null's Addons for modern Hypixel SkyBlock (Fabric, Minecraft 1.21+).
 *
 * <p>Client-side and advisory: it reads the public Bazaar/Election API and shows
 * you flips, craft flips and the current Mayor's economy — a movable HUD and
 * item-tooltip annotations — never automating play. All work is async and cached
 * (see {@link BazaarClient}); the game thread only reads results, and only on
 * SkyBlock. Telemetry is opt-in and off by default (see {@link Telemetry}).
 */
public final class NullsAddonsClient implements ClientModInitializer {

    @Override
    public void onInitializeClient() {
        NullsConfig.load();
        Keybinds.register();
        BazaarClient.get().start();
        Telemetry.get().init();

        HudRenderCallback.EVENT.register(new HudOverlay());
        ItemTooltipCallback.EVENT.register(new TooltipHandler());
        ClientTickEvents.END_CLIENT_TICK.register(Keybinds::onEndTick);
        ClientCommandRegistrationCallback.EVENT.register(Commands::register);
        ClientLifecycleEvents.CLIENT_STOPPING.register(client -> {
            BazaarClient.get().shutdown();
            Telemetry.get().flushBlocking();
        });
    }
}
