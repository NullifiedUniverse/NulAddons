package com.nullifieduniverse.nulladdons;

import com.nullifieduniverse.nulladdons.client.BazaarTooltip;
import com.nullifieduniverse.nulladdons.client.HudOverlay;
import com.nullifieduniverse.nulladdons.client.NullsCommand;
import com.nullifieduniverse.nulladdons.client.NullsConfig;
import com.nullifieduniverse.nulladdons.client.NullsKeybinds;
import com.nullifieduniverse.nulladdons.net.BazaarClient;
import net.minecraftforge.client.ClientCommandHandler;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.common.event.FMLInitializationEvent;
import net.minecraftforge.fml.common.event.FMLPreInitializationEvent;

/**
 * Null's Addons — a lightweight, client-side Hypixel SkyBlock companion that
 * brings the Bazaar-flipping engine in game.
 *
 * <p>Everything heavy (network + flip computation) runs on a background thread in
 * {@link BazaarClient}; the client thread only reads cached results, and only
 * when the player is actually on SkyBlock. So it costs nothing when you don't
 * need it, and shows up seamlessly when you do — a movable HUD of the top flips
 * and inline flip numbers on Bazaar item tooltips.
 */
@Mod(modid = NullsAddonsMod.MODID, name = NullsAddonsMod.NAME,
     version = NullsAddonsMod.VERSION, clientSideOnly = true,
     guiFactory = "com.nullifieduniverse.nulladdons.client.NullsGuiFactory")
public class NullsAddonsMod {
    public static final String MODID = "nulladdons";
    public static final String NAME = "Null's Addons";
    public static final String VERSION = "1.0.0";

    @Mod.EventHandler
    public void preInit(FMLPreInitializationEvent event) {
        NullsConfig.init(event.getSuggestedConfigurationFile());
    }

    @Mod.EventHandler
    public void init(FMLInitializationEvent event) {
        NullsKeybinds.register();
        ClientCommandHandler.instance.registerCommand(new NullsCommand());  // /nulladdons
        MinecraftForge.EVENT_BUS.register(new HudOverlay());
        MinecraftForge.EVENT_BUS.register(new BazaarTooltip());
        MinecraftForge.EVENT_BUS.register(new NullsKeybinds());
        MinecraftForge.EVENT_BUS.register(new NullsConfig());  // listens for config edits

        BazaarClient.get().setConfig(NullsConfig.engineConfig());
        BazaarClient.get().start();
    }
}
