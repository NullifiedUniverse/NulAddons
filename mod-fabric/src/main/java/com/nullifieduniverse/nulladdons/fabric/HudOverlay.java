package com.nullifieduniverse.nulladdons.fabric;

import com.nullifieduniverse.nulladdons.core.Anim;
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

    private static final long FADE_MS = 260L;    // panel materialises this fast
    private static final long PULSE_MS = 1400L;  // header shimmer period when cracked
    private static final double CRACKED = 0.25;  // margin that earns the shimmer

    /** When the panel most recently began showing (0 = hidden), for the fade-in. */
    private long shownAt = 0L;

    @Override
    public void onHudRender(DrawContext context, RenderTickCounter tickCounter) {
        if (!NullsConfig.hudEnabled) return;
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc.options.hudHidden) return;                 // respect F1 (transient: keep the fade)
        if (mc.currentScreen != null) return;             // not while a menu is open (transient)
        if (!SkyblockState.onSkyblock()) { shownAt = 0L; return; }

        List<Flip> flips = BazaarClient.get().getTopFlips();
        if (flips == null || flips.isEmpty()) { shownAt = 0L; return; }

        long now = System.currentTimeMillis();
        if (shownAt == 0L) shownAt = now;                 // first appearance -> start the fade
        draw(context, mc.textRenderer, flips, now - shownAt, now);
    }

    private void draw(DrawContext ctx, TextRenderer tr, List<Flip> flips, long elapsed, long now) {
        int count = Math.min(Math.max(1, NullsConfig.hudCount), flips.size());
        List<String> lines = new ArrayList<String>(count + 1);
        lines.add("§6§lNull's Addons §r§7· top flips");
        boolean cracked = false;
        for (int i = 0; i < count; i++) {
            Flip f = flips.get(i);
            if (f.margin >= CRACKED) cracked = true;
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

        double alpha = Anim.fadeAlpha(elapsed, FADE_MS);
        int header = 0x400062FF;                          // subtle blue header tint
        if (cracked) {                                    // gently breathe while spicy
            int a = (int) Math.round(Anim.lerp(0x30, 0x80, Anim.pulse(now, PULSE_MS)));
            header = (a << 24) | 0x0062FF;
        }

        // Backdrop + header fade in (text stays crisp via its own § colours).
        ctx.fill(x, y, x + width + pad * 2, y + height, Anim.withAlpha(0x90000000, alpha));
        ctx.fill(x, y, x + width + pad * 2, y + lineH + pad, Anim.withAlpha(header, alpha));

        int ty = y + pad;
        for (String s : lines) {
            ctx.drawTextWithShadow(tr, s, x + pad, ty, 0xFFFFFF);
            ty += lineH;
        }
    }
}
