package com.nullifieduniverse.nulladdons.fabric;

import com.nullifieduniverse.nulladdons.core.Flair;
import com.nullifieduniverse.nulladdons.core.Flip;
import com.nullifieduniverse.nulladdons.core.Format;
import net.fabricmc.fabric.api.client.rendering.v1.HudRenderCallback;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.font.TextRenderer;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.render.RenderTickCounter;

import java.util.ArrayList;
import java.util.List;

/**
 * The movable top-flips panel. Registered on {@code HudRenderCallback}, it draws
 * only while you're playing on SkyBlock with the HUD enabled and cached flips
 * present — it returns on the first cheap check otherwise, so the render path is
 * free the rest of the time. One {@code fill} + a few precomputed strings.
 */
public final class HudOverlay implements HudRenderCallback {

    @Override
    public void onHudRender(DrawContext context, RenderTickCounter tickCounter) {
        if (!NullsConfig.hudEnabled) return;
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc.options.hudHidden) return;                 // respect F1
        if (mc.currentScreen != null) return;             // not while a menu is open
        if (!SkyblockState.onSkyblock()) return;

        List<Flip> flips = BazaarClient.get().getTopFlips();
        if (flips == null || flips.isEmpty()) return;

        draw(context, mc.textRenderer, flips);
    }

    private void draw(DrawContext ctx, TextRenderer tr, List<Flip> flips) {
        int count = Math.min(Math.max(1, NullsConfig.hudCount), flips.size());
        List<String> lines = new ArrayList<String>(count + 1);
        lines.add("§6§lNull's Addons §r§7· top flips");
        for (int i = 0; i < count; i++) {
            Flip f = flips.get(i);
            String hype = Flair.crackedLabel(f.margin);
            lines.add("§f" + Format.niceName(f.productId) + " "
                    + Format.marginColor(f.margin) + Format.pct(f.margin)
                    + " §7· §b" + Format.coins(f.coinsPerHour) + "§7/hr"
                    + (hype.isEmpty() ? "" : " " + hype));
        }

        int pad = 3;
        int width = 0;
        for (String s : lines) width = Math.max(width, tr.getWidth(s));
        int x = NullsConfig.hudX;
        int y = NullsConfig.hudY;
        int lineH = tr.fontHeight + 1;
        int height = lines.size() * lineH + pad * 2 - 1;

        ctx.fill(x, y, x + width + pad * 2, y + height, 0x90000000);          // backdrop
        ctx.fill(x, y, x + width + pad * 2, y + lineH + pad, 0x400062FF);     // header tint

        int ty = y + pad;
        for (String s : lines) {
            ctx.drawTextWithShadow(tr, s, x + pad, ty, 0xFFFFFF);
            ty += lineH;
        }
    }
}
