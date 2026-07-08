package com.nullifieduniverse.nulladdons.client;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiScreen;
import net.minecraftforge.fml.client.IModGuiFactory;

import java.util.Set;

/** Wires the "Config" button next to Null's Addons in the Mods menu. */
public class NullsGuiFactory implements IModGuiFactory {
    public void initialize(Minecraft minecraftInstance) {}

    public Class<? extends GuiScreen> mainConfigGuiClass() {
        return NullsConfigGui.class;
    }

    public Set<IModGuiFactory.RuntimeOptionCategoryElement> runtimeGuiCategories() {
        return null;
    }

    public IModGuiFactory.RuntimeOptionGuiHandler getHandlerFor(
            IModGuiFactory.RuntimeOptionCategoryElement element) {
        return null;
    }
}
