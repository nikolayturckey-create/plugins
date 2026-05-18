package ru.projecterror.kitacat;

import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabCompleter;
import org.bukkit.Location;
import org.bukkit.entity.Cat;
import org.bukkit.entity.Player;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

public final class KitaCommand implements CommandExecutor, TabCompleter {
    private static final String PREFIX = "§dКита §7» §f";
    private final KitaCatPlugin plugin;
    private final KitaManager kitaManager;
    private final KitaMoodManager moodManager;

    public KitaCommand(KitaCatPlugin plugin, KitaManager kitaManager, KitaMoodManager moodManager) {
        this.plugin = plugin;
        this.kitaManager = kitaManager;
        this.moodManager = moodManager;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (args.length == 0) {
            sender.sendMessage(PREFIX + "Используй: /kita <spawn|remove|tp|sit|follow|reload|status>");
            return true;
        }

        String sub = args[0].toLowerCase(Locale.ROOT);
        switch (sub) {
            case "spawn" -> handleSpawn(sender);
            case "remove" -> handleRemove(sender);
            case "tp" -> handleTeleport(sender);
            case "sit" -> handleSit(sender);
            case "follow" -> handleFollow(sender);
            case "reload" -> handleReload(sender);
            case "status" -> handleStatus(sender);
            default -> sender.sendMessage(PREFIX + "Неизвестная команда. Используй: /kita <spawn|remove|tp|sit|follow|reload|status>");
        }
        return true;
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        if (args.length != 1) {
            return List.of();
        }
        List<String> options = new ArrayList<>();
        if (hasAdmin(sender)) {
            options.addAll(List.of("spawn", "remove", "tp", "sit", "follow", "reload", "status"));
        } else if (sender instanceof Player player && kitaManager.isOwner(player)) {
            options.addAll(List.of("tp", "sit", "follow", "status"));
        } else if (plugin.getConfig().getBoolean("status.public", true)) {
            options.add("status");
        }
        String prefix = args[0].toLowerCase(Locale.ROOT);
        return options.stream().filter(option -> option.startsWith(prefix)).toList();
    }

    private void handleSpawn(CommandSender sender) {
        if (!hasAdmin(sender)) {
            deny(sender);
            return;
        }
        if (!(sender instanceof Player player)) {
            sender.sendMessage(PREFIX + "Эту команду нужно выполнить от имени игрока.");
            return;
        }
        boolean existed = kitaManager.getKita() != null;
        kitaManager.spawnNear(player);
        sender.sendMessage(PREFIX + (existed ? "уже была рядом — я аккуратно перенёс её к тебе." : "появилась рядом с тобой."));
    }

    private void handleRemove(CommandSender sender) {
        if (!hasAdmin(sender)) {
            deny(sender);
            return;
        }
        boolean removed = kitaManager.removeKita();
        sender.sendMessage(PREFIX + (removed ? "мягко исчезла. Её можно вернуть командой /kita spawn." : "сейчас не создана."));
    }

    private void handleTeleport(CommandSender sender) {
        if (!(sender instanceof Player player)) {
            sender.sendMessage(PREFIX + "Эту команду нужно выполнить от имени игрока.");
            return;
        }
        if (!hasOwnerAccess(player)) {
            deny(sender);
            return;
        }
        if (kitaManager.teleportTo(player)) {
            sender.sendMessage(PREFIX + "подбежала поближе.");
        } else {
            sender.sendMessage(PREFIX + "пока не создана. Администратор может использовать /kita spawn.");
        }
    }

    private void handleSit(CommandSender sender) {
        if (!(sender instanceof Player player) || !hasOwnerAccess(player)) {
            deny(sender);
            return;
        }
        kitaManager.setSitting(true);
        sender.sendMessage(PREFIX + "садится и спокойно ждёт рядом.");
    }

    private void handleFollow(CommandSender sender) {
        if (!(sender instanceof Player player) || !hasOwnerAccess(player)) {
            deny(sender);
            return;
        }
        kitaManager.setFollowing(true);
        sender.sendMessage(PREFIX + "встаёт и снова идёт за хозяином.");
    }

    private void handleReload(CommandSender sender) {
        if (!hasAdmin(sender)) {
            deny(sender);
            return;
        }
        plugin.reloadPluginConfig();
        sender.sendMessage(PREFIX + "config.yml перезагружен.");
    }


    private void handleStatus(CommandSender sender) {
        if (!canSeeStatus(sender)) {
            deny(sender);
            return;
        }
        Cat cat = kitaManager.getKita();
        if (cat == null) {
            sender.sendMessage(PREFIX + "Кита сейчас не создана. Используй /kita spawn.");
            return;
        }

        String ownerName = kitaManager.getOwnerName();
        Player owner = kitaManager.getOwnerPlayer();
        String distance = "хозяин оффлайн";
        if (owner != null && owner.getWorld().equals(cat.getWorld())) {
            distance = Math.round(cat.getLocation().distance(owner.getLocation())) + " блоков";
        }
        Location location = cat.getLocation();
        sender.sendMessage("§dКита");
        sender.sendMessage("§7Хозяин: §f" + ownerName);
        sender.sendMessage("§7Состояние: §f" + kitaManager.getStateDescription());
        sender.sendMessage("§7Настроение: §f" + moodManager.getMood().getDisplayName());
        sender.sendMessage("§7Мир: §f" + (location.getWorld() == null ? "неизвестно" : location.getWorld().getName()));
        sender.sendMessage("§7Расстояние до хозяина: §f" + distance);
        sender.sendMessage("§7Последняя позиция: §f"
                + location.getBlockX() + " " + location.getBlockY() + " " + location.getBlockZ());
    }

    private boolean canSeeStatus(CommandSender sender) {
        if (plugin.getConfig().getBoolean("status.public", true)) {
            return true;
        }
        if (hasAdmin(sender)) {
            return true;
        }
        return sender instanceof Player player && kitaManager.isOwner(player);
    }

    private boolean hasAdmin(CommandSender sender) {
        return sender.hasPermission("kita.admin") || sender.isOp();
    }

    private boolean hasOwnerAccess(Player player) {
        return hasAdmin(player) || kitaManager.isOwner(player);
    }

    private void deny(CommandSender sender) {
        sender.sendMessage(PREFIX + "у тебя нет прав для этой команды.");
    }
}
