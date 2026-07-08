package com.nullifieduniverse.nulladdons.client;

import net.minecraft.client.Minecraft;
import net.minecraft.client.settings.KeyBinding;
import net.minecraft.util.ChatComponentText;
import net.minecraftforge.fml.client.registry.ClientRegistry;
import net.minecraftforge.fml.common.eventhandler.SubscribeEvent;
import net.minecraftforge.fml.common.gameevent.InputEvent;
import org.lwjgl.input.Keyboard;

/** One key to toggle the HUD (default: N), grouped under "Null's Addons". */
public final class NullsKeybinds {
    public static KeyBinding toggleHud;

    public static void register() {
        toggleHud = new KeyBinding("Toggle Null's Addons HUD", Keyboard.KEY_N,
                "Null's Addons");
        ClientRegistry.registerKeyBinding(toggleHud);
    }

    @SubscribeEvent
    public void onKey(InputEvent.KeyInputEvent event) {
        if (toggleHud != null && toggleHud.isPressed()) {
            NullsConfig.hudEnabled = !NullsConfig.hudEnabled;
            NullsConfig.save();
            Minecraft mc = Minecraft.getMinecraft();
            if (mc.thePlayer != null) {
                mc.thePlayer.addChatMessage(new ChatComponentText(
                        "§6[Null's Addons] §7HUD "
                                + (NullsConfig.hudEnabled ? "§ashown" : "§chidden")));
            }
        }
    }
}
