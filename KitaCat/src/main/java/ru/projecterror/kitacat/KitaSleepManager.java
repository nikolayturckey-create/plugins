package ru.projecterror.kitacat;

import org.bukkit.Location;
import org.bukkit.Sound;
import org.bukkit.World;
import org.bukkit.entity.Cat;
import org.bukkit.entity.Player;
import org.bukkit.scheduler.BukkitTask;

import java.util.concurrent.ThreadLocalRandom;

public final class KitaSleepManager {
    private static final String PREFIX = "§dКита §7» §f";

    private final KitaCatPlugin plugin;
    private final KitaManager kitaManager;
    private final KitaMoodManager moodManager;
    private final KitaDangerManager dangerManager;
    private BukkitTask task;
    private long lastMessageMillis;

    public KitaSleepManager(KitaCatPlugin plugin, KitaManager kitaManager, KitaMoodManager moodManager, KitaDangerManager dangerManager) {
        this.plugin = plugin;
        this.kitaManager = kitaManager;
        this.moodManager = moodManager;
        this.dangerManager = dangerManager;
    }

    public void start() {
        stop();
        if (!plugin.getConfig().getBoolean("sleep.enabled", true)) {
            return;
        }
        task = plugin.getServer().getScheduler().runTaskTimer(plugin, this::tickSafely, 20L * 15L, 20L * 30L);
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

    private void tickSafely() {
        try {
            tick();
        } catch (RuntimeException exception) {
            plugin.getLogger().fine("Kita sleep check skipped: " + exception.getMessage());
        }
    }

    private void tick() {
        Cat cat = kitaManager.getKita();
        if (cat == null || cat.getWorld() == null || !isNight(cat.getWorld())) {
            return;
        }
        if (dangerManager.hasDangerNearby()) {
            moodManager.setMood(KitaMood.SCARED);
            return;
        }
        Player owner = kitaManager.getOwnerPlayer();
        boolean activelyFollowing = kitaManager.isFollowing() && owner != null && owner.getWorld().equals(cat.getWorld())
                && cat.getLocation().distanceSquared(owner.getLocation()) > 4.0 * 4.0;
        if (activelyFollowing) {
            return;
        }

        moodManager.setMood(KitaMood.SLEEPY);
        cat.setSitting(true);
        if (ThreadLocalRandom.current().nextInt(100) < 30) {
            cat.getWorld().playSound(cat.getLocation(), Sound.ENTITY_CAT_PURR, 0.25F, 0.75F);
        }

        long now = System.currentTimeMillis();
        long cooldown = Math.max(60L, plugin.getConfig().getLong("sleep.message-cooldown-seconds", 300L)) * 1000L;
        if (now - lastMessageMillis < cooldown || ThreadLocalRandom.current().nextInt(100) >= 35) {
            return;
        }
        lastMessageMillis = now;
        kitaManager.getNearbyPlayers(10.0).forEach(player -> player.sendMessage(PREFIX + "свернулась клубочком и тихо мурчит во сне."));
    }

    private boolean isNight(World world) {
        long time = world.getTime();
        long start = plugin.getConfig().getLong("sleep.start-time", 13000L);
        long end = plugin.getConfig().getLong("sleep.end-time", 23000L);
        if (start <= end) {
            return time >= start && time <= end;
        }
        return time >= start || time <= end;
    }
}
