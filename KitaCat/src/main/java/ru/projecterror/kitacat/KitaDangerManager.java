package ru.projecterror.kitacat;

import org.bukkit.Location;
import org.bukkit.Sound;
import org.bukkit.entity.Cat;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Monster;
import org.bukkit.entity.Player;
import org.bukkit.scheduler.BukkitTask;

public final class KitaDangerManager {
    private static final String PREFIX = "§dКита §7» §f";

    private final KitaCatPlugin plugin;
    private final KitaManager kitaManager;
    private final KitaMoodManager moodManager;
    private BukkitTask task;
    private long lastMessageMillis;

    public KitaDangerManager(KitaCatPlugin plugin, KitaManager kitaManager, KitaMoodManager moodManager) {
        this.plugin = plugin;
        this.kitaManager = kitaManager;
        this.moodManager = moodManager;
    }

    public void start() {
        stop();
        if (!plugin.getConfig().getBoolean("danger.enabled", true)) {
            return;
        }
        task = plugin.getServer().getScheduler().runTaskTimer(plugin, this::tickSafely, 20L * 5L, 20L * 5L);
    }

    public void restart() {
        start();
    }

    public void stop() {
        if (task != null) {
            task.cancel();
            task = null;
        }
    }

    public boolean hasDangerNearby() {
        Cat cat = kitaManager.getKita();
        return cat != null && hasDangerNearby(cat, plugin.getConfig().getDouble("danger.radius", 10.0));
    }

    private void tickSafely() {
        try {
            tick();
        } catch (RuntimeException exception) {
            plugin.getLogger().fine("Kita danger check skipped: " + exception.getMessage());
        }
    }

    private void tick() {
        Cat cat = kitaManager.getKita();
        if (cat == null || !hasDangerNearby(cat, plugin.getConfig().getDouble("danger.radius", 10.0))) {
            return;
        }
        moodManager.setMood(KitaMood.SCARED);
        long now = System.currentTimeMillis();
        long cooldown = Math.max(10L, plugin.getConfig().getLong("danger.cooldown-seconds", 60L)) * 1000L;
        if (now - lastMessageMillis < cooldown) {
            return;
        }
        lastMessageMillis = now;

        cat.getWorld().playSound(cat.getLocation(), Sound.ENTITY_CAT_AMBIENT, 0.6F, 0.7F);
        cat.setSitting(true);
        if (plugin.getConfig().getBoolean("danger.teleport-to-owner", true)) {
            Player owner = kitaManager.getOwnerPlayer();
            if (owner != null && owner.getWorld().equals(cat.getWorld())) {
                cat.teleport(kitaManager.findSafeNear(owner.getLocation(), 3));
            }
        }
        kitaManager.getNearbyPlayers(10.0).forEach(player -> player.sendMessage(PREFIX + "прижимает ушки и прячется ближе к хозяину."));
    }

    private boolean hasDangerNearby(Cat cat, double radius) {
        Location location = cat.getLocation();
        for (Entity entity : cat.getWorld().getNearbyEntities(location, radius, radius, radius)) {
            if (entity instanceof Monster && entity.isValid() && !entity.isDead()) {
                return true;
            }
        }
        return false;
    }
}
