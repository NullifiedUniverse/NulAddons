package com.nullifieduniverse.nulladdons.client;

import net.minecraft.command.CommandBase;
import net.minecraft.command.CommandException;
import net.minecraft.command.ICommandSender;
import net.minecraft.util.ChatComponentText;

/**
 * The {@code /nulladdons} client chat command (parity with the Fabric build).
 * Registered on the Forge {@code ClientCommandHandler}, so it runs entirely
 * client-side and works on any server. Type {@code /nulladdons help} for the list.
 *
 * <p>Everything here just flips a display setting — nothing touches the game or
 * automates play.
 */
public final class NullsCommand extends CommandBase {

    @Override
    public String getCommandName() {
        return "nulladdons";
    }

    @Override
    public String getCommandUsage(ICommandSender sender) {
        return "/nulladdons help";
    }

    /** Client command: always usable, no permission level required. */
    @Override
    public int getRequiredPermissionLevel() {
        return 0;
    }

    @Override
    public boolean canCommandSenderUseCommand(ICommandSender sender) {
        return true;
    }

    @Override
    public void processCommand(ICommandSender sender, String[] args) throws CommandException {
        String sub = args.length == 0 ? "help" : args[0].toLowerCase();

        if ("hud".equals(sub)) {
            NullsConfig.hudEnabled = !NullsConfig.hudEnabled;
            NullsConfig.save();
            reply(sender, "HUD " + onOff(NullsConfig.hudEnabled));

        } else if ("tooltip".equals(sub)) {
            NullsConfig.tooltipEnabled = !NullsConfig.tooltipEnabled;
            NullsConfig.save();
            reply(sender, "Bazaar tooltips " + onOff(NullsConfig.tooltipEnabled));

        } else if ("count".equals(sub)) {
            Integer n = tryInt(args, 1);
            if (n == null || n < 1 || n > 10) {
                reply(sender, "§cUsage: /nulladdons count <1-10>");
            } else {
                NullsConfig.hudCount = n;
                NullsConfig.save();
                reply(sender, "HUD now shows §f" + n + "§7 flip(s).");
            }

        } else if ("move".equals(sub)) {
            Integer x = tryInt(args, 1);
            Integer y = tryInt(args, 2);
            if (x == null || y == null || x < 0 || y < 0) {
                reply(sender, "§cUsage: /nulladdons move <x> <y>");
            } else {
                NullsConfig.hudX = x;
                NullsConfig.hudY = y;
                NullsConfig.save();
                reply(sender, "HUD moved to §f" + x + ", " + y + "§7.");
            }

        } else {
            help(sender);
        }
    }

    private void help(ICommandSender sender) {
        reply(sender, "§lcommands §r§7(you can also press §fN§7 to toggle the HUD)");
        line(sender, "help", "this list");
        line(sender, "hud", "show/hide the top-flips panel");
        line(sender, "tooltip", "toggle flip numbers on Bazaar item tooltips");
        line(sender, "count <1-10>", "how many flips the HUD shows");
        line(sender, "move <x> <y>", "reposition the HUD panel");
        sender.addChatMessage(new ChatComponentText(
                "§8Config in the Mods menu · advisory only — it never plays for you"));
    }

    private static String onOff(boolean b) {
        return b ? "§ashown" : "§chidden";
    }

    private static Integer tryInt(String[] args, int i) {
        if (i >= args.length) return null;
        try {
            return Integer.valueOf(Integer.parseInt(args[i]));
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private static void line(ICommandSender sender, String cmd, String desc) {
        sender.addChatMessage(new ChatComponentText("  §e/nulladdons " + cmd + " §8— §7" + desc));
    }

    private static void reply(ICommandSender sender, String text) {
        sender.addChatMessage(new ChatComponentText("§6[Null's Addons] §r" + text));
    }
}
