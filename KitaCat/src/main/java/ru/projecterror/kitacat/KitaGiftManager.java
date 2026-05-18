package ru.projecterror.kitacat;

import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Cat;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.scheduler.BukkitTask;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ThreadLocalRandom;

public final class KitaGiftManager {
    private static final String PREFIX = "§dКита §7» §f";

    private final KitaCatPlugin plugin;
    private final KitaManager kitaManager;
    private BukkitTask task;

    public KitaGiftManager(KitaCatPlugin plugin, KitaManager kitaManager) {
        this.plugin = plugin;
        this.kitaManager = kitaManager;
    }

    public void start() {
        stop();
        if (!plugin.getConfig().getBoolean("gifts.enabled", true)) {
            return;
        }
        long interval = Math.max(60L, plugin.getConfig().getLong("gifts.interval-seconds", 600L)) * 20L;
        task = plugin.getServer().getScheduler().runTaskTimer(plugin, this::tryGiftSafely, interval, interval);
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

    private void tryGiftSafely() {
        try {
            tryGift();
        } catch (RuntimeException exception) {
            plugin.getLogger().fine("Kita gift skipped: " + exception.getMessage());
        }
    }

    private void tryGift() {
        Cat cat = kitaManager.getKita();
        Player owner = kitaManager.getOwnerPlayer();
        if (cat == null || owner == null || !owner.getWorld().equals(cat.getWorld())) {
            return;
        }
        if (cat.getLocation().distanceSquared(owner.getLocation()) > 6.0 * 6.0) {
            return;
        }
        int chance = Math.max(0, Math.min(100, plugin.getConfig().getInt("gifts.chance-percent", 8)));
        if (ThreadLocalRandom.current().nextInt(100) >= chance) {
            return;
        }

        List<Gift> gifts = loadGifts();
        if (gifts.isEmpty()) {
            return;
        }
        Gift gift = gifts.get(ThreadLocalRandom.current().nextInt(gifts.size()));
        ItemStack stack = new ItemStack(gift.material(), gift.amount());
        Map<Integer, ItemStack> leftovers = owner.getInventory().addItem(stack);
        leftovers.values().forEach(item -> owner.getWorld().dropItemNaturally(owner.getLocation(), item));

        Location particleLocation = cat.getLocation().clone().add(0, 0.8, 0);
        cat.getWorld().playSound(cat.getLocation(), Sound.ENTITY_CAT_PURR, 0.8F, 1.2F);
        cat.getWorld().spawnParticle(Particle.HEART, particleLocation, 5, 0.3, 0.3, 0.3, 0.01);
        owner.sendMessage(PREFIX + gift.message());
        kitaManager.face(cat, owner.getLocation());
    }

    private List<Gift> loadGifts() {
        List<Gift> gifts = new ArrayList<>();
        List<?> list = plugin.getConfig().getList("gifts.items", List.of());
        for (Object raw : list) {
            String materialName = null;
            int amount = 1;
            String message = "Кита принесла тебе маленький подарок.";
            if (raw instanceof ConfigurationSection section) {
                materialName = section.getString("material");
                amount = section.getInt("amount", 1);
                message = section.getString("message", message);
            } else if (raw instanceof Map<?, ?> map) {
                Object material = map.get("material");
                Object rawAmount = map.get("amount");
                Object rawMessage = map.get("message");
                materialName = material == null ? null : String.valueOf(material);
                if (rawAmount instanceof Number number) {
                    amount = number.intValue();
                } else if (rawAmount != null) {
                    try {
                        amount = Integer.parseInt(String.valueOf(rawAmount));
                    } catch (NumberFormatException ignored) {
                        amount = 1;
                    }
                }
                if (rawMessage != null) {
                    message = String.valueOf(rawMessage);
                }
            }
            Material material = materialName == null ? null : Material.matchMaterial(materialName);
            if (material != null && material.isItem()) {
                gifts.add(new Gift(material, Math.max(1, Math.min(16, amount)), message));
            }
        }
        return gifts;
    }

    private record Gift(Material material, int amount, String message) {
    }
}
