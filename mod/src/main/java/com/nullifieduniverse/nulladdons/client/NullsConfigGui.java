package com.nullifieduniverse.nulladdons.client;

import com.nullifieduniverse.nulladdons.NullsAddonsMod;
import net.minecraft.client.gui.GuiScreen;
import net.minecraftforge.fml.client.config.ConfigElement;
import net.minecraftforge.fml.client.config.GuiConfig;

/** A standard Forge config screen generated from the mod's config category. */
public class NullsConfigGui extends GuiConfig {
    public NullsConfigGui(GuiScreen parent) {
        super(parent,
              new ConfigElement(NullsConfig.getConfig().getCategory("general"))
                      .getChildElements(),
              NullsAddonsMod.MODID, false, false, "Null's Addons");
    }
}
