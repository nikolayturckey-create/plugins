package ru.projecterror.kitacat;

import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.NamespacedKey;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.World;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Cat;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.Player;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.scheduler.BukkitTask;
import org.bukkit.util.Vector;

import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;

public final class KitaManager {
    private static final String CHAT_PREFIX = "§dКита §7» §f";

    private final KitaCatPlugin plugin;
    private final NamespacedKey kitaKey;
    private Cat kita;
    private boolean following;
    private boolean sitting;
    private Location lastSafeLocation;
    private BukkitTask followTask;
    private BukkitTask saveTask;
    private BukkitTask soundTask;

    public KitaManager(KitaCatPlugin plugin) {
        this.plugin = plugin;
        this.kitaKey = new NamespacedKey(plugin, "kita_cat");
        this.following = plugin.getDataConfig().getBoolean("kita.following", true);
        this.sitting = plugin.getDataConfig().getBoolean("kita.sitting", false);
    }

    public void startTasks() {
        followTask = Bukkit.getScheduler().runTaskTimer(plugin, this::tickFollowAndSafety, 20L, 20L);
        saveTask = Bukkit.getScheduler().runTaskTimer(plugin, this::saveKitaState, 20L * 60L, 20L * 60L);
        soundTask = Bukkit.getScheduler().runTaskTimer(plugin, this::tickAmbientSound, 20L * 20L, Math.max(20L, getSoundIntervalSeconds() * 20L));
    }

    public void shutdownSave() {
        cancelTask(followTask);
        cancelTask(saveTask);
        cancelTask(soundTask);
        saveKitaState();
    }

    public void restoreOrCreateKita() {
        Cat found = findBySavedUuid().or(() -> findTaggedKita()).orElse(null);
        if (found != null && found.isValid()) {
            this.kita = found;
            configureKita(found);
            applyMode();
            saveKitaState();
            return;
        }

        Location location = getLastLocation();
        if (location == null) {
            Player owner = getOwnerPlayer();
            if (owner != null) {
                location = findSafeNear(owner.getLocation(), 3);
            }
        }
        if (location == null) {
            location = getFallbackWorld().getSpawnLocation();
        }
        spawnKita(findSafeNear(location, 4));
    }

    public Cat spawnNear(Player player) {
        Location location = findSafeNear(player.getLocation(), 3);
        if (kita != null && kita.isValid()) {
            kita.teleport(location);
            configureKita(kita);
            applyMode();
            saveKitaState();
            return kita;
        }
        return spawnKita(location);
    }

    public Cat spawnKita(Location location) {
        if (location == null || location.getWorld() == null) {
            location = getFallbackWorld().getSpawnLocation();
        }
        Location safe = findSafeNear(location, 5);
        Cat cat = (Cat) safe.getWorld().spawnEntity(safe, EntityType.CAT);
        this.kita = cat;
        configureKita(cat);
        applyMode();
        plugin.getDataConfig().set("kita.spawned", true);
        saveKitaState();
        return cat;
    }

    public boolean removeKita() {
        Cat cat = getKita();
        if (cat == null) {
            plugin.getDataConfig().set("kita.spawned", false);
            plugin.getDataConfig().set("kita.uuid", "");
            plugin.saveData();
            return false;
        }
        cat.remove();
        this.kita = null;
        plugin.getDataConfig().set("kita.spawned", false);
        plugin.getDataConfig().set("kita.uuid", "");
        plugin.saveData();
        return true;
    }

    public boolean teleportTo(Player player) {
        Cat cat = getKita();
        if (cat == null) {
            return false;
        }
        cat.teleport(findSafeNear(player.getLocation(), 3));
        applyMode();
        saveKitaState();
        return true;
    }

    public void setSitting(boolean sitting) {
        this.sitting = sitting;
        this.following = !sitting;
        applyMode();
        saveKitaState();
    }

    public void setFollowing(boolean following) {
        this.following = following;
        this.sitting = !following;
        applyMode();
        saveKitaState();
    }

    public boolean isOwner(Player player) {
        if (player == null) {
            return false;
        }
        String owner = getOwnerName();
        return player.getName().equalsIgnoreCase(owner) || player.hasPermission("kita.owner");
    }

    public boolean isKita(Entity entity) {
        if (!(entity instanceof Cat cat)) {
            return false;
        }
        if (kita != null && entity.getUniqueId().equals(kita.getUniqueId())) {
            return true;
        }
        Byte marker = cat.getPersistentDataContainer().get(kitaKey, PersistentDataType.BYTE);
        return marker != null && marker == (byte) 1;
    }

    public Cat getKita() {
        if (kita != null && kita.isValid() && !kita.isDead()) {
            return kita;
        }
        kita = findBySavedUuid().or(() -> findTaggedKita()).orElse(null);
        return kita;
    }

    public Player getOwnerPlayer() {
        return Bukkit.getPlayerExact(getOwnerName());
    }

    public String getOwnerName() {
        return plugin.getConfig().getString("kita.owner", "haamster185");
    }

    public String getKitaName() {
        return plugin.getConfig().getString("kita.name", "Кита");
    }

    public void face(Entity entity, Location target) {
        if (entity == null || target == null || entity.getWorld() == null || target.getWorld() == null || !entity.getWorld().equals(target.getWorld())) {
            return;
        }
        Location from = entity.getLocation();
        Vector direction = target.toVector().subtract(from.toVector());
        if (direction.lengthSquared() < 0.0001) {
            return;
        }
        from.setDirection(direction);
        entity.teleport(from);
    }

    public void playInteraction(Player player, boolean owner) {
        Cat cat = getKita();
        if (cat == null) {
            return;
        }
        if (owner) {
            player.sendMessage(CHAT_PREFIX + "узнаёт хозяина и тихо мурчит.");
            cat.getWorld().playSound(cat.getLocation(), Sound.ENTITY_CAT_PURR, 0.8F, 1.2F);
            cat.getWorld().spawnParticle(Particle.HEART, cat.getLocation().add(0, 0.8, 0), 5, 0.3, 0.3, 0.3, 0.01);
        } else {
            player.sendMessage(CHAT_PREFIX + "смотрит на тебя осторожно. Она не злая, просто слишком многое видела.");
            cat.getWorld().playSound(cat.getLocation(), Sound.ENTITY_CAT_AMBIENT, 0.7F, 1.0F);
        }
        face(cat, player.getLocation());
    }

    public List<Player> getNearbyPlayers(double radius) {
        Cat cat = getKita();
        if (cat == null || cat.getWorld() == null) {
            return List.of();
        }
        double radiusSquared = radius * radius;
        Location location = cat.getLocation();
        return cat.getWorld().getPlayers().stream()
                .filter(player -> player.getLocation().distanceSquared(location) <= radiusSquared)
                .toList();
    }

    public Optional<Player> getNearestPlayer(double radius) {
        Cat cat = getKita();
        if (cat == null) {
            return Optional.empty();
        }
        Location location = cat.getLocation();
        double radiusSquared = radius * radius;
        return cat.getWorld().getPlayers().stream()
                .filter(player -> player.getLocation().distanceSquared(location) <= radiusSquared)
                .min(Comparator.comparingDouble(player -> player.getLocation().distanceSquared(location)));
    }

    public Location findSafeNear(Location center, int radius) {
        if (center == null || center.getWorld() == null) {
            center = getFallbackWorld().getSpawnLocation();
        }
        World world = center.getWorld();
        Location base = center.clone();
        for (int attempt = 0; attempt < 32; attempt++) {
            int dx = attempt == 0 ? 0 : ThreadLocalRandom.current().nextInt(-radius, radius + 1);
            int dz = attempt == 0 ? 0 : ThreadLocalRandom.current().nextInt(-radius, radius + 1);
            int x = base.getBlockX() + dx;
            int z = base.getBlockZ() + dz;
            int y = Math.min(world.getMaxHeight() - 2, Math.max(world.getMinHeight() + 1, base.getBlockY() + 3));
            Location candidate = new Location(world, x + 0.5, y, z + 0.5, base.getYaw(), base.getPitch());
            while (candidate.getY() > world.getMinHeight() + 1 && candidate.getBlock().isPassable() && candidate.clone().subtract(0, 1, 0).getBlock().isPassable()) {
                candidate.subtract(0, 1, 0);
            }
            Location feet = candidate.clone();
            Location head = feet.clone().add(0, 1, 0);
            Location ground = feet.clone().subtract(0, 1, 0);
            if (!ground.getBlock().isPassable() && feet.getBlock().isPassable() && head.getBlock().isPassable()) {
                return feet;
            }
        }
        return world.getSpawnLocation();
    }

    public void saveKitaState() {
        Cat cat = getKita();
        if (cat != null) {
            Location location = cat.getLocation();
            if (isSafe(location)) {
                lastSafeLocation = location.clone();
            }
            plugin.getDataConfig().set("kita.uuid", cat.getUniqueId().toString());
            plugin.getDataConfig().set("kita.spawned", true);
            saveLocation(location);
        }
        plugin.getDataConfig().set("kita.sitting", sitting);
        plugin.getDataConfig().set("kita.following", following);
        plugin.saveData();
    }

    public Location getLastLocation() {
        ConfigurationSection section = plugin.getDataConfig().getConfigurationSection("kita.last-location");
        if (section == null) {
            return null;
        }
        World world = Bukkit.getWorld(section.getString("world", plugin.getConfig().getString("kita.world", "world")));
        if (world == null) {
            world = getFallbackWorld();
        }
        return new Location(
                world,
                section.getDouble("x"),
                section.getDouble("y"),
                section.getDouble("z"),
                (float) section.getDouble("yaw"),
                (float) section.getDouble("pitch")
        );
    }

    public Location getLastSafeLocation() {
        if (lastSafeLocation != null && isSafe(lastSafeLocation)) {
            return lastSafeLocation.clone();
        }
        Location stored = getLastLocation();
        if (stored != null && isSafe(stored)) {
            return stored;
        }
        return getFallbackWorld().getSpawnLocation();
    }

    private void configureKita(Cat cat) {
        cat.getPersistentDataContainer().set(kitaKey, PersistentDataType.BYTE, (byte) 1);
        cat.setCustomName(getKitaName());
        cat.setCustomNameVisible(true);
        cat.setAdult();
        cat.setAgeLock(true);
        cat.setBreed(false);
        cat.setRemoveWhenFarAway(false);
        cat.setPersistent(true);
        cat.setInvulnerable(plugin.getConfig().getBoolean("protection.invulnerable", true));
        cat.setCollidable(true);
        cat.setCanPickupItems(false);
        cat.setTamed(true);
        cat.setOwner(Bukkit.getOfflinePlayer(getOwnerName()));
    }

    private void applyMode() {
        Cat cat = getKita();
        if (cat == null) {
            return;
        }
        cat.setSitting(sitting);
        cat.setAI(true);
        if (sitting) {
            cat.setVelocity(new Vector(0, 0, 0));
        }
    }

    private void tickFollowAndSafety() {
        Cat cat = getKita();
        if (cat == null) {
            return;
        }
        cat.setFireTicks(0);
        if (!isSafe(cat.getLocation()) || cat.getLocation().getY() <= cat.getWorld().getMinHeight()) {
            Player owner = getOwnerPlayer();
            Location target = owner != null ? findSafeNear(owner.getLocation(), 3) : getLastSafeLocation();
            cat.teleport(target);
            return;
        }
        if (!plugin.getConfig().getBoolean("follow.enabled", true) || !following || sitting) {
            return;
        }
        Player owner = getOwnerPlayer();
        if (owner == null || !owner.getWorld().equals(cat.getWorld())) {
            return;
        }
        double distance = cat.getLocation().distance(owner.getLocation());
        double teleportDistance = plugin.getConfig().getDouble("follow.teleport-distance", 35.0);
        double minDistance = plugin.getConfig().getDouble("follow.min-distance", 3.0);
        double maxDistance = plugin.getConfig().getDouble("follow.max-distance", 18.0);
        if (distance > teleportDistance) {
            cat.teleport(findSafeNear(owner.getLocation(), 3));
            return;
        }
        if (distance > minDistance) {
            cat.setSitting(false);
            Vector direction = owner.getLocation().toVector().subtract(cat.getLocation().toVector());
            direction.setY(0);
            if (direction.lengthSquared() > 0.01) {
                double speed = Math.max(0.15, Math.min(0.55, plugin.getConfig().getDouble("follow.speed", 1.2) * 0.22));
                if (distance > maxDistance) {
                    speed *= 1.35;
                }
                cat.setVelocity(direction.normalize().multiply(speed).setY(cat.isOnGround() ? 0.08 : cat.getVelocity().getY()));
                face(cat, owner.getLocation());
            }
        }
    }

    private void tickAmbientSound() {
        Cat cat = getKita();
        if (cat == null || !plugin.getConfig().getBoolean("sounds.meow-enabled", true)) {
            return;
        }
        int chance = plugin.getConfig().getInt("sounds.meow-chance-percent", 3);
        if (ThreadLocalRandom.current().nextInt(100) < Math.max(0, Math.min(100, chance))) {
            cat.getWorld().playSound(cat.getLocation(), Sound.ENTITY_CAT_AMBIENT, 0.45F, 1.0F);
        }
    }

    private Optional<Cat> findBySavedUuid() {
        String rawUuid = plugin.getDataConfig().getString("kita.uuid", "");
        if (rawUuid == null || rawUuid.isBlank()) {
            return Optional.empty();
        }
        try {
            UUID uuid = UUID.fromString(rawUuid);
            for (World world : Bukkit.getWorlds()) {
                Entity entity = world.getEntity(uuid);
                if (entity instanceof Cat cat && cat.isValid()) {
                    return Optional.of(cat);
                }
            }
        } catch (IllegalArgumentException ignored) {
            return Optional.empty();
        }
        return Optional.empty();
    }

    private Optional<Cat> findTaggedKita() {
        for (World world : Bukkit.getWorlds()) {
            for (Cat cat : world.getEntitiesByClass(Cat.class)) {
                if (isKita(cat) && cat.isValid()) {
                    return Optional.of(cat);
                }
            }
        }
        return Optional.empty();
    }

    private void saveLocation(Location location) {
        if (location == null || location.getWorld() == null) {
            return;
        }
        plugin.getDataConfig().set("kita.last-location.world", location.getWorld().getName());
        plugin.getDataConfig().set("kita.last-location.x", location.getX());
        plugin.getDataConfig().set("kita.last-location.y", location.getY());
        plugin.getDataConfig().set("kita.last-location.z", location.getZ());
        plugin.getDataConfig().set("kita.last-location.yaw", location.getYaw());
        plugin.getDataConfig().set("kita.last-location.pitch", location.getPitch());
    }

    private boolean isSafe(Location location) {
        if (location == null || location.getWorld() == null) {
            return false;
        }
        World world = location.getWorld();
        if (location.getY() <= world.getMinHeight() || location.getY() >= world.getMaxHeight() - 1) {
            return false;
        }
        return location.getBlock().isPassable()
                && location.clone().add(0, 1, 0).getBlock().isPassable()
                && !location.clone().subtract(0, 1, 0).getBlock().isPassable();
    }

    private World getFallbackWorld() {
        World configured = Bukkit.getWorld(plugin.getConfig().getString("kita.world", "world"));
        if (configured != null) {
            return configured;
        }
        Player firstPlayer = Bukkit.getOnlinePlayers().stream().findFirst().orElse(null);
        if (firstPlayer != null) {
            return firstPlayer.getWorld();
        }
        return Bukkit.getWorlds().stream().findFirst().orElseThrow(() -> new IllegalStateException("No worlds loaded"));
    }

    private long getSoundIntervalSeconds() {
        return Math.max(1L, plugin.getConfig().getLong("sounds.interval-seconds", 20L));
    }

    private void cancelTask(BukkitTask task) {
        if (task != null) {
            task.cancel();
        }
    }
}
