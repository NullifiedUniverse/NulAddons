package com.nullifieduniverse.nulladdons.fabric;

import net.fabricmc.fabric.api.client.keybinding.v1.KeyBindingHelper;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.option.KeyBinding;
import net.minecraft.client.util.InputUtil;
import net.minecraft.text.Text;
import org.lwjgl.glfw.GLFW;

/** One key (default N) toggles the HUD. */
public final class Keybinds {
    public static KeyBinding toggleHud;

    private Keybinds() {}

    public static void register() {
        toggleHud = KeyBindingHelper.registerKeyBinding(new KeyBinding(
                "key.nulladdons.toggle_hud", InputUtil.Type.KEYSYM,
                GLFW.GLFW_KEY_N, "Null's Addons"));
    }

    public static void onEndTick(MinecraftClient mc) {
        if (toggleHud == null) return;
        while (toggleHud.wasPressed()) {
            NullsConfig.hudEnabled = !NullsConfig.hudEnabled;
            NullsConfig.save();
            if (mc.player != null) {
                mc.player.sendMessage(Text.literal("§6[Null's Addons] §7HUD "
                        + (NullsConfig.hudEnabled ? "§ashown" : "§chidden")), false);
            }
        }
    }
}
