package com.nullifieduniverse.nulladdons.client;

import com.nullifieduniverse.nulladdons.core.Anim;
import com.nullifieduniverse.nulladdons.core.Flip;
import com.nullifieduniverse.nulladdons.core.Format;
import com.nullifieduniverse.nulladdons.net.BazaarClient;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.FontRenderer;
import net.minecraft.client.gui.Gui;
import net.minecraftforge.client.event.RenderGameOverlayEvent;
import net.minecraftforge.fml.common.eventhandler.SubscribeEvent;

import java.util.ArrayList;
import java.util.List;

/**
 * A compact, movable panel that lists the current top flips — the "shows up when
 * needed" surface. It renders <em>only</em> while you're playing on SkyBlock with
 * the HUD enabled and cached data present; otherwise the handler returns on the
 * first cheap check, so there is no cost in menus, other games, or singleplayer.
 * It draws nothing but a translucent rectangle and a few precomputed strings.
 */
public final class HudOverlay extends Gui {

    private static final long FADE_MS = 260L;    // panel materialises this fast
    private static final long PULSE_MS = 1400L;  // header shimmer period when cracked
    private static final double CRACKED = 0.25;  // margin that earns the shimmer

    /** When the panel most recently began showing (0 = hidden), for the fade-in. */
    private long shownAt = 0L;

    @SubscribeEvent
    public void onRenderOverlay(RenderGameOverlayEvent.Post event) {
        if (event.type != RenderGameOverlayEvent.ElementType.ALL) return;
        if (!NullsConfig.hudEnabled) return;

        Minecraft mc = Minecraft.getMinecraft();
        if (mc.gameSettings.showDebugInfo) return;      // yield to F3 (transient: keep the fade)
        if (!SkyblockState.onSkyblock()) { shownAt = 0L; return; }

        List<Flip> flips = BazaarClient.get().getTopFlips();
        if (flips == null || flips.isEmpty()) { shownAt = 0L; return; }

        long now = System.currentTimeMillis();
        if (shownAt == 0L) shownAt = now;               // first appearance -> start the fade
        draw(mc, flips, now - shownAt, now);
    }

    private void draw(Minecraft mc, List<Flip> flips, long elapsed, long now) {
        FontRenderer fr = mc.fontRendererObj;
        int count = Math.min(Math.max(1, NullsConfig.hudCount), flips.size());

        List<String> lines = new ArrayList<String>(count + 1);
        lines.add("§6§lNull's Addons §r§7· top flips");
        boolean cracked = false;
        for (int i = 0; i < count; i++) {
            Flip f = flips.get(i);
            if (f.margin >= CRACKED) cracked = true;
            lines.add("§f" + Format.niceName(f.productId) + " "
                    + Format.marginColor(f.margin) + Format.pct(f.margin)
                    + " §7· §b" + Format.coins(f.coinsPerHour) + "§7/hr");
        }

        int pad = 3;
        int width = 0;
        for (String s : lines) width = Math.max(width, fr.getStringWidth(s));
        int x = NullsConfig.hudX;
        int y = NullsConfig.hudY;
        int lineH = fr.FONT_HEIGHT + 1;
        int height = lines.size() * lineH + pad * 2 - 1;

        double alpha = Anim.fadeAlpha(elapsed, FADE_MS);
        int header = 0x400062FF;                        // subtle blue header tint
        if (cracked) {                                  // gently breathe while spicy
            int a = (int) Math.round(Anim.lerp(0x30, 0x80, Anim.pulse(now, PULSE_MS)));
            header = (a << 24) | 0x0062FF;
        }

        // Backdrop + header fade in (text stays crisp via its own § colours).
        drawRect(x, y, x + width + pad * 2, y + height, Anim.withAlpha(0x90000000, alpha));
        drawRect(x, y, x + width + pad * 2, y + lineH + pad, Anim.withAlpha(header, alpha));

        int ty = y + pad;
        for (String s : lines) {
            fr.drawStringWithShadow(s, x + pad, ty, 0xFFFFFF);
            ty += lineH;
        }
    }
}
