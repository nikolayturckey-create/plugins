package ru.projecterror.kitacat;

import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Sound;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.player.PlayerMoveEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.util.Vector;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

public final class KitaAntiCheat implements Listener {
    private static final String PREFIX = "§cKitaAC §7» §f";
    private static final double TPS_COMPENSATION = 1.35;

    private final KitaCatPlugin plugin;
    private final Map<UUID, PlayerCheckState> states = new HashMap<>();

    public KitaAntiCheat(KitaCatPlugin plugin) {
        this.plugin = plugin;
    }

    public void reportStatus(CommandSender sender) {
        sender.sendMessage(PREFIX + "статус: " + (isEnabled() ? "§aвключён" : "§cвыключен"));
        sender.sendMessage(PREFIX + "порог скорости: " + getDouble("speed.max-blocks-per-second", 8.6)
                + ", reach: " + getDouble("combat.max-reach", 3.35)
                + ", VL: " + getInt("punishments.setback-violations", 4));
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onMove(PlayerMoveEvent event) {
        if (!isEnabled()) {
            return;
        }
        Player player = event.getPlayer();
        if (isExempt(player) || event.getFrom().getWorld() == null || event.getTo() == null || event.getTo().getWorld() == null
                || !event.getFrom().getWorld().equals(event.getTo().getWorld())) {
            rememberSafeLocation(player, event.getTo());
            return;
        }

        PlayerCheckState state = states.computeIfAbsent(player.getUniqueId(), ignored -> new PlayerCheckState(event.getFrom()));
        long now = System.currentTimeMillis();
        double elapsedSeconds = Math.max(0.05, (now - state.lastMoveMillis) / 1000.0);
        state.lastMoveMillis = now;

        Location from = event.getFrom();
        Location to = event.getTo();
        double horizontal = horizontalDistance(from, to);
        double horizontalSpeed = horizontal / elapsedSeconds;
        double verticalGain = to.getY() - from.getY();

        boolean suspiciousSpeed = horizontalSpeed > getAllowedHorizontalSpeed(player);
        boolean suspiciousClimb = verticalGain > getDouble("speed.max-vertical-gain", 0.95) && !isNearClimbable(to);

        if (suspiciousSpeed || suspiciousClimb) {
            String check = suspiciousSpeed ? "Speed" : "Fly/Step";
            flag(player, state, check, Math.max(horizontalSpeed, verticalGain));
            if (state.violations >= getInt("punishments.setback-violations", 4) && state.lastSafeLocation != null) {
                event.setTo(state.lastSafeLocation.clone());
                player.setVelocity(new Vector(0, Math.min(0, player.getVelocity().getY()), 0));
                player.playSound(player.getLocation(), Sound.BLOCK_NOTE_BLOCK_BASS, 0.45F, 0.65F);
            }
            return;
        }

        state.violations = Math.max(0, state.violations - getInt("decay-per-clean-move", 1));
        if (isSafeGround(to)) {
            state.lastSafeLocation = to.clone();
        }
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onAttack(EntityDamageByEntityEvent event) {
        if (!isEnabled() || !(event.getDamager() instanceof Player player) || isExempt(player) || !(event.getEntity() instanceof Player target)) {
            return;
        }
        if (!player.getWorld().equals(target.getWorld())) {
            return;
        }
        double reach = player.getEyeLocation().distance(target.getLocation().add(0, 0.9, 0));
        if (reach <= getDouble("combat.max-reach", 3.35)) {
            return;
        }
        PlayerCheckState state = states.computeIfAbsent(player.getUniqueId(), ignored -> new PlayerCheckState(player.getLocation()));
        flag(player, state, "Reach", reach);
        if (state.violations >= getInt("punishments.cancel-hit-violations", 2)) {
            event.setCancelled(true);
        }
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent event) {
        states.remove(event.getPlayer().getUniqueId());
    }

    private void flag(Player player, PlayerCheckState state, String check, double value) {
        state.violations++;
        long now = System.currentTimeMillis();
        if (now - state.lastAlertMillis < getInt("alerts.cooldown-millis", 2500)) {
            return;
        }
        state.lastAlertMillis = now;
        String message = PREFIX + player.getName() + " подозрение " + check + " §7(value=" + String.format(java.util.Locale.ROOT, "%.2f", value)
                + ", vl=" + state.violations + ")";
        Bukkit.getOnlinePlayers().stream()
                .filter(online -> online.hasPermission("kita.anticheat.alerts") || online.isOp())
                .forEach(online -> online.sendMessage(message));
        plugin.getLogger().warning(message.replace('§', '&'));
    }

    private void rememberSafeLocation(Player player, Location location) {
        if (location != null && isSafeGround(location)) {
            states.computeIfAbsent(player.getUniqueId(), ignored -> new PlayerCheckState(location)).lastSafeLocation = location.clone();
        }
    }

    private boolean isEnabled() {
        return plugin.getConfig().getBoolean("anticheat.enabled", true);
    }

    private boolean isExempt(Player player) {
        return player.hasPermission("kita.anticheat.bypass")
                || player.getGameMode() == GameMode.CREATIVE
                || player.getGameMode() == GameMode.SPECTATOR
                || player.isFlying()
                || player.isGliding()
                || player.isInsideVehicle()
                || player.isRiptiding()
                || player.getAllowFlight();
    }

    private double getAllowedHorizontalSpeed(Player player) {
        double base = getDouble("speed.max-blocks-per-second", 8.6);
        if (player.isSprinting()) {
            base += getDouble("speed.sprint-buffer", 1.25);
        }
        if (player.hasPotionEffect(org.bukkit.potion.PotionEffectType.SPEED)) {
            base += getDouble("speed.potion-buffer", 2.4);
        }
        return base * TPS_COMPENSATION;
    }

    private boolean isNearClimbable(Location location) {
        Material type = location.getBlock().getType();
        Material below = location.clone().subtract(0, 1, 0).getBlock().getType();
        return type == Material.LADDER || type == Material.VINE || type.name().contains("VINES") || type.name().contains("SCAFFOLDING")
                || below == Material.SLIME_BLOCK || below == Material.HONEY_BLOCK;
    }

    private boolean isSafeGround(Location location) {
        return location.getBlock().isPassable() && !location.clone().subtract(0, 1, 0).getBlock().isPassable();
    }

    private double horizontalDistance(Location from, Location to) {
        double dx = to.getX() - from.getX();
        double dz = to.getZ() - from.getZ();
        return Math.sqrt(dx * dx + dz * dz);
    }

    private double getDouble(String path, double fallback) {
        return plugin.getConfig().getDouble("anticheat." + path, fallback);
    }

    private int getInt(String path, int fallback) {
        return plugin.getConfig().getInt("anticheat." + path, fallback);
    }

    private static final class PlayerCheckState {
        private Location lastSafeLocation;
        private long lastMoveMillis = System.currentTimeMillis();
        private long lastAlertMillis;
        private int violations;

        private PlayerCheckState(Location lastSafeLocation) {
            this.lastSafeLocation = lastSafeLocation == null ? null : lastSafeLocation.clone();
        }
    }
}
