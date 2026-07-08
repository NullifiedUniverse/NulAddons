package com.nullifieduniverse.nulladdons.client;

import com.nullifieduniverse.nulladdons.core.Flip;
import com.nullifieduniverse.nulladdons.core.Format;
import com.nullifieduniverse.nulladdons.net.BazaarClient;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.inventory.GuiChest;
import net.minecraft.item.ItemStack;
import net.minecraft.nbt.NBTTagCompound;
import net.minecraftforge.event.entity.player.ItemTooltipEvent;
import net.minecraftforge.fml.common.eventhandler.SubscribeEvent;

import java.util.List;

/**
 * Appends live flip numbers to the tooltip of any Bazaar-tradable item you hover
 * inside a SkyBlock menu — the most seamless surface of all: you're already
 * looking at the item, and the buy-order/sell-offer/margin/coins-per-hour just
 * appear beneath its lore, styled like native SkyBlock text.
 *
 * <p>Identity comes from the item's own {@code ExtraAttributes.id} NBT (the same
 * id space as the Bazaar API), so it's exact. If the id isn't a Bazaar product
 * the tooltip is simply left untouched — never wrong.
 */
public final class BazaarTooltip {

    @SubscribeEvent
    public void onItemTooltip(ItemTooltipEvent event) {
        if (!NullsConfig.tooltipEnabled || event.itemStack == null) return;
        Minecraft mc = Minecraft.getMinecraft();
        if (!(mc.currentScreen instanceof GuiChest)) return;  // only in menus (Bazaar)
        if (!SkyblockState.onSkyblock()) return;

        String id = extractSkyblockId(event.itemStack);
        if (id == null) return;
        Flip flip = BazaarClient.get().flipFor(id);
        if (flip == null) return;

        List<String> tip = event.toolTip;
        tip.add("");
        tip.add("§6§lNull's Addons");
        tip.add(" §7Buy order §a" + Format.price(flip.buyOrder)
                + " §7→ Sell offer §a" + Format.price(flip.sellOffer));
        String line = " §7Margin " + Format.marginColor(flip.margin)
                + Format.pct(flip.margin) + " §7after tax";
        if (flip.coinsPerHour > 0) {
            line += " §7· §b" + Format.coins(flip.coinsPerHour) + "§7/hr";
        }
        tip.add(line);
        if (flip.unitProfit <= 0) {
            tip.add(" §cSpread doesn't cover the tax right now.");
        }
    }

    private static String extractSkyblockId(ItemStack stack) {
        if (stack == null || !stack.hasTagCompound()) return null;
        NBTTagCompound tag = stack.getTagCompound();
        if (!tag.hasKey("ExtraAttributes")) return null;
        String id = tag.getCompoundTag("ExtraAttributes").getString("id");
        return (id == null || id.isEmpty()) ? null : id;
    }
}
