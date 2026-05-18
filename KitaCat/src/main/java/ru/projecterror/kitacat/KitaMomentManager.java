package ru.projecterror.kitacat;

import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Cat;
import org.bukkit.entity.Player;
import org.bukkit.scheduler.BukkitTask;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.ThreadLocalRandom;

public final class KitaMomentManager {
    private static final String PREFIX = "§dКита §7» §f";

    private final KitaCatPlugin plugin;
    private final KitaManager kitaManager;
    private BukkitTask task;

    public KitaMomentManager(KitaCatPlugin plugin, KitaManager kitaManager) {
        this.plugin = plugin;
        this.kitaManager = kitaManager;
    }

    public void start() {
        stop();
        if (!plugin.getConfig().getBoolean("moments.enabled", true)) {
            return;
        }
        long interval = Math.max(60L, plugin.getConfig().getLong("moments.interval-seconds", 180L) * 20L);
        task = plugin.getServer().getScheduler().runTaskTimer(plugin, this::playRandomMomentSafely, interval, interval);
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

    private void playRandomMomentSafely() {
        try {
            playRandomMoment();
        } catch (RuntimeException exception) {
            plugin.getLogger().fine("Kita moment skipped: " + exception.getMessage());
        }
    }

    private void playRandomMoment() {
        Cat cat = kitaManager.getKita();
        if (cat == null || cat.getWorld() == null) {
            return;
        }
        double radius = plugin.getConfig().getDouble("moments.radius", 10.0);
        List<Player> nearbyPlayers = kitaManager.getNearbyPlayers(radius);
        if (nearbyPlayers.isEmpty()) {
            return;
        }

        List<Moment> moments = loadMoments(selectSection());
        if (moments.isEmpty()) {
            moments = loadMoments("moments.random");
        }
        if (moments.isEmpty()) {
            return;
        }

        Moment moment = moments.get(ThreadLocalRandom.current().nextInt(moments.size()));
        nearbyPlayers.forEach(player -> player.sendMessage(PREFIX + moment.text()));
        playEmotion(cat, moment.emotion(), radius);
    }

    private String selectSection() {
        Player owner = kitaManager.getOwnerPlayer();
        if (owner != null) {
            return "moments.owner-online";
        }
        if (ThreadLocalRandom.current().nextBoolean()) {
            return "moments.owner-offline";
        }
        return "moments.random";
    }

    private List<Moment> loadMoments(String path) {
        List<?> rawList = plugin.getConfig().getList(path, List.of());
        List<Moment> moments = new ArrayList<>();
        for (Object value : rawList) {
            if (value instanceof ConfigurationSection section) {
                addMoment(moments, section.getString("text"), section.getString("emotion"));
            } else if (value instanceof java.util.Map<?, ?> map) {
                Object text = map.get("text");
                Object emotion = map.get("emotion");
                addMoment(moments, text == null ? null : String.valueOf(text), emotion == null ? null : String.valueOf(emotion));
            }
        }
        return moments;
    }

    private void addMoment(List<Moment> moments, String text, String emotion) {
        if (text == null || text.isBlank()) {
            return;
        }
        moments.add(new Moment(text, KitaEmotion.fromString(emotion)));
    }

    private void playEmotion(Cat cat, KitaEmotion emotion, double radius) {
        Location location = cat.getLocation().clone().add(0, 0.8, 0);
        Optional<Player> nearest = kitaManager.getNearestPlayer(radius);
        Player owner = kitaManager.getOwnerPlayer();

        switch (emotion) {
            case HAPPY -> {
                cat.setSitting(false);
                cat.getWorld().playSound(cat.getLocation(), Sound.ENTITY_CAT_PURR, 0.75F, 1.35F);
                cat.getWorld().spawnParticle(Particle.HEART, location, 4, 0.3, 0.3, 0.3, 0.01);
                nearest.ifPresent(player -> kitaManager.face(cat, player.getLocation()));
            }
            case SAD -> {
                cat.setSitting(true);
                cat.getWorld().playSound(cat.getLocation(), Sound.ENTITY_CAT_AMBIENT, 0.45F, 0.65F);
                cat.getWorld().spawnParticle(Particle.CLOUD, location, 5, 0.25, 0.2, 0.25, 0.01);
            }
            case WAITING -> {
                cat.setSitting(true);
                cat.getWorld().playSound(cat.getLocation(), Sound.ENTITY_CAT_AMBIENT, 0.35F, 0.9F);
                nearest.ifPresentOrElse(player -> kitaManager.face(cat, player.getLocation()), () -> kitaManager.face(cat, kitaManager.getLastSafeLocation()));
            }
            case TRUST -> {
                cat.getWorld().playSound(cat.getLocation(), Sound.ENTITY_CAT_PURR, 0.65F, 1.1F);
                cat.getWorld().spawnParticle(ThreadLocalRandom.current().nextBoolean() ? Particle.HEART : Particle.VILLAGER_HAPPY, location, 4, 0.3, 0.3, 0.3, 0.01);
                if (owner != null && owner.getWorld().equals(cat.getWorld())) {
                    kitaManager.face(cat, owner.getLocation());
                } else {
                    nearest.ifPresent(player -> kitaManager.face(cat, player.getLocation()));
                }
            }
            case LONELY -> {
                cat.setSitting(true);
                cat.getWorld().playSound(cat.getLocation(), Sound.ENTITY_CAT_AMBIENT, 0.35F, 0.55F);
                cat.getWorld().spawnParticle(Particle.WHITE_ASH, location, 6, 0.3, 0.2, 0.3, 0.01);
            }
            case SLEEPY -> {
                cat.setSitting(true);
                cat.getWorld().playSound(cat.getLocation(), Sound.ENTITY_CAT_PURR, 0.35F, 0.75F);
                plugin.getServer().getScheduler().runTaskLater(plugin, () -> {
                    if (kitaManager.getKita() != null) {
                        cat.setSitting(false);
                    }
                }, 20L * 6L);
            }
        }
    }

    private record Moment(String text, KitaEmotion emotion) {
    }
}
