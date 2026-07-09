package com.nullifieduniverse.nulladdons.fabric;

import com.nullifieduniverse.nulladdons.core.CraftFlip;
import com.nullifieduniverse.nulladdons.core.Flair;
import com.nullifieduniverse.nulladdons.core.Flip;
import com.nullifieduniverse.nulladdons.core.Format;
import net.fabricmc.fabric.api.client.item.v1.ItemTooltipCallback;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.screen.ingame.HandledScreen;
import net.minecraft.component.DataComponentTypes;
import net.minecraft.component.type.NbtComponent;
import net.minecraft.item.Item;
import net.minecraft.item.ItemStack;
import net.minecraft.item.tooltip.TooltipType;
import net.minecraft.nbt.NbtCompound;
import net.minecraft.text.Text;

import java.util.List;

/**
 * Appends live flip (and, if enabled, craft-flip) numbers under the lore of any
 * Bazaar-tradable item you hover in a SkyBlock menu. Identity comes from the
 * item's own {@code custom_data} -> {@code ExtraAttributes.id} (same id space as
 * the Bazaar API), so it's exact; non-Bazaar items are left untouched.
 */
public final class TooltipHandler implements ItemTooltipCallback {

    @Override
    public void getTooltip(ItemStack stack, Item.TooltipContext tooltipContext,
                           TooltipType type, List<Text> lines) {
        if (!NullsConfig.tooltipEnabled || stack == null || stack.isEmpty()) return;
        MinecraftClient mc = MinecraftClient.getInstance();
        if (!(mc.currentScreen instanceof HandledScreen)) return;   // only in menus (Bazaar)
        if (!SkyblockState.onSkyblock()) return;

        String id = skyblockId(stack);
        if (id == null) return;

        Flip flip = BazaarClient.get().flipFor(id);
        CraftFlip craft = NullsConfig.showCraft ? BazaarClient.get().craftFor(id) : null;
        if (flip == null && craft == null) return;

        lines.add(Text.literal(""));
        lines.add(Text.literal("§6§lNull's Addons"));
        if (flip != null) {
            lines.add(Text.literal(" §7Buy §a" + Format.price(flip.buyOrder)
                    + " §7→ Sell §a" + Format.price(flip.sellOffer)));
            String m = " §7Flip " + Format.marginColor(flip.margin)
                    + Format.pct(flip.margin) + " §7after tax";
            if (flip.coinsPerHour > 0) m += " §7· §b" + Format.coins(flip.coinsPerHour) + "§7/hr";
            String hype = Flair.crackedLabel(flip.margin);
            if (!hype.isEmpty()) m += " " + hype;
            lines.add(Text.literal(m));
            if (flip.unitProfit <= 0) {
                lines.add(Text.literal(" §cSpread doesn't cover the tax right now."));
            }
        }
        if (craft != null && craft.unitProfit > 0) {
            lines.add(Text.literal(" §7Craft from mats: "
                    + Format.marginColor(craft.margin) + Format.pct(craft.margin)
                    + " §7(§a" + Format.coins(craft.unitProfit) + "§7/ea)"));
        }
        Telemetry.get().onTooltip();
    }

    private static String skyblockId(ItemStack stack) {
        NbtComponent data = stack.get(DataComponentTypes.CUSTOM_DATA);
        if (data == null) return null;
        NbtCompound nbt = data.copyNbt();
        if (nbt == null || !nbt.contains("ExtraAttributes")) return null;
        String id = nbt.getCompound("ExtraAttributes").getString("id");
        return (id == null || id.isEmpty()) ? null : id;
    }
}
