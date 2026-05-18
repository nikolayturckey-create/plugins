package ru.projecterror.kitacat;

import org.bukkit.Location;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityCombustEvent;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.entity.EntityDeathEvent;
import org.bukkit.event.entity.EntityTargetEvent;
import org.bukkit.event.player.PlayerInteractEntityEvent;

public final class KitaListener implements Listener {
    private final KitaCatPlugin plugin;
    private final KitaManager kitaManager;

    public KitaListener(KitaCatPlugin plugin, KitaManager kitaManager) {
        this.plugin = plugin;
        this.kitaManager = kitaManager;
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onDamage(EntityDamageEvent event) {
        Entity entity = event.getEntity();
        if (!kitaManager.isKita(entity)) {
            return;
        }
        event.setCancelled(true);
        entity.setFireTicks(0);
        if (event.getCause() == EntityDamageEvent.DamageCause.VOID || entity.getLocation().getY() <= entity.getWorld().getMinHeight()) {
            Player owner = kitaManager.getOwnerPlayer();
            Location target = owner != null ? kitaManager.findSafeNear(owner.getLocation(), 3) : kitaManager.getLastSafeLocation();
            entity.teleport(target);
        }
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onCombust(EntityCombustEvent event) {
        if (!kitaManager.isKita(event.getEntity())) {
            return;
        }
        event.setCancelled(true);
        event.getEntity().setFireTicks(0);
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onTarget(EntityTargetEvent event) {
        if (event.getTarget() != null && kitaManager.isKita(event.getTarget())) {
            event.setCancelled(true);
            event.setTarget(null);
        }
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onDeath(EntityDeathEvent event) {
        if (!kitaManager.isKita(event.getEntity())) {
            return;
        }
        event.getDrops().clear();
        event.setDroppedExp(0);
        plugin.getServer().getScheduler().runTask(plugin, kitaManager::restoreOrCreateKita);
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onInteract(PlayerInteractEntityEvent event) {
        if (!kitaManager.isKita(event.getRightClicked())) {
            return;
        }
        event.setCancelled(true);
        kitaManager.playInteraction(event.getPlayer(), kitaManager.isDirectOwner(event.getPlayer()));
    }
}
