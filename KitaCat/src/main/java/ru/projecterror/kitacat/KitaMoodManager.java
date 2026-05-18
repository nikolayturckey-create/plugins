package ru.projecterror.kitacat;

import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.entity.Cat;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Monster;
import org.bukkit.entity.Player;
import org.bukkit.scheduler.BukkitTask;

import java.util.concurrent.ThreadLocalRandom;

public final class KitaMoodManager {
    private final KitaCatPlugin plugin;
    private final KitaManager kitaManager;
    private KitaMood mood = KitaMood.CALM;
    private BukkitTask task;

    public KitaMoodManager(KitaCatPlugin plugin, KitaManager kitaManager) {
        this.plugin = plugin;
        this.kitaManager = kitaManager;
    }

    public void start() {
        stop();
        task = plugin.getServer().getScheduler().runTaskTimer(plugin, this::refreshMoodSafely, 20L * 5L, 20L * 10L);
    }

    public void stop() {
        if (task != null) {
            task.cancel();
            task = null;
        }
    }

    public void restart() {
        start();
    }

    public KitaMood getMood() {
        return mood;
    }

    public void setMood(KitaMood mood) {
        if (mood != null) {
            this.mood = mood;
        }
    }

    private void refreshMoodSafely() {
        try {
            refreshMood();
        } catch (RuntimeException exception) {
            plugin.getLogger().fine("Kita mood refresh skipped: " + exception.getMessage());
        }
    }

    private void refreshMood() {
        Cat cat = kitaManager.getKita();
        if (cat == null || cat.getWorld() == null) {
            mood = KitaMood.CALM;
            return;
        }
        if (hasMonsterNearby(cat, plugin.getConfig().getDouble("danger.radius", 10.0))) {
            mood = KitaMood.SCARED;
            return;
        }
        if (isNight(cat.getWorld()) && !kitaManager.isFollowing()) {
            mood = KitaMood.SLEEPY;
            return;
        }

        Player owner = kitaManager.getOwnerPlayer();
        if (owner == null || !owner.getWorld().equals(cat.getWorld())) {
            mood = KitaMood.LONELY;
            return;
        }

        double distance = owner.getLocation().distance(cat.getLocation());
        if (distance <= plugin.getConfig().getDouble("follow.min-distance", 3.0) + 4.0) {
            mood = ThreadLocalRandom.current().nextInt(100) < 55 ? KitaMood.HAPPY : KitaMood.CALM;
        } else if (distance > plugin.getConfig().getDouble("follow.max-distance", 18.0)) {
            mood = KitaMood.LONELY;
        } else {
            mood = KitaMood.CALM;
        }
    }

    private boolean hasMonsterNearby(Cat cat, double radius) {
        Location location = cat.getLocation();
        for (Entity entity : cat.getWorld().getNearbyEntities(location, radius, radius, radius)) {
            if (entity instanceof Monster && entity.isValid() && !entity.isDead()) {
                return true;
            }
        }
        return false;
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
