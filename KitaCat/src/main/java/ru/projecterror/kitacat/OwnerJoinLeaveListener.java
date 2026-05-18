package ru.projecterror.kitacat;

import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.entity.Cat;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;

public final class OwnerJoinLeaveListener implements Listener {
    private static final String PREFIX = "§dКита §7» §f";

    private final KitaManager kitaManager;
    private final KitaMoodManager moodManager;

    public OwnerJoinLeaveListener(KitaManager kitaManager, KitaMoodManager moodManager) {
        this.kitaManager = kitaManager;
        this.moodManager = moodManager;
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onOwnerJoin(PlayerJoinEvent event) {
        Player player = event.getPlayer();
        if (!kitaManager.isDirectOwner(player)) {
            return;
        }
        Cat cat = kitaManager.getKita();
        if (cat == null) {
            return;
        }
        if (!cat.getWorld().equals(player.getWorld()) || cat.getLocation().distanceSquared(player.getLocation()) > 18.0 * 18.0) {
            cat.teleport(kitaManager.findSafeNear(player.getLocation(), 3));
        } else {
            kitaManager.face(cat, player.getLocation());
        }
        moodManager.setMood(KitaMood.HAPPY);
        cat.getWorld().playSound(cat.getLocation(), Sound.ENTITY_CAT_PURR, 0.9F, 1.25F);
        cat.getWorld().spawnParticle(Particle.HEART, cat.getLocation().clone().add(0, 0.8, 0), 6, 0.3, 0.3, 0.3, 0.01);
        player.sendMessage(PREFIX + "Кита услышала знакомые шаги и поспешила к тебе.");
        kitaManager.getNearbyPlayers(10.0).stream()
                .filter(nearby -> !nearby.equals(player))
                .forEach(nearby -> nearby.sendMessage(PREFIX + "подняла голову, будто сразу узнала шаги хозяина."));
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onOwnerQuit(PlayerQuitEvent event) {
        Player player = event.getPlayer();
        if (!kitaManager.isDirectOwner(player)) {
            return;
        }
        Cat cat = kitaManager.getKita();
        if (cat == null) {
            return;
        }
        cat.setSitting(true);
        moodManager.setMood(KitaMood.LONELY);
        cat.getWorld().playSound(cat.getLocation(), Sound.ENTITY_CAT_AMBIENT, 0.35F, 0.75F);
        kitaManager.getNearbyPlayers(10.0).forEach(nearby -> nearby.sendMessage(PREFIX + "тихо садится на месте, где он только что стоял."));
        kitaManager.saveKitaState();
    }
}
