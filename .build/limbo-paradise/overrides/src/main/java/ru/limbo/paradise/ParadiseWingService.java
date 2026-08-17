package ru.limbo.paradise;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import org.bukkit.Material;
import org.bukkit.entity.Item;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityPickupItemEvent;
import org.bukkit.event.entity.EntityToggleGlideEvent;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryCloseEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.event.player.PlayerChangedWorldEvent;
import org.bukkit.event.player.PlayerDropItemEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerRespawnEvent;
import org.bukkit.event.player.PlayerSwapHandItemsEvent;
import org.bukkit.event.player.PlayerTeleportEvent;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;
import org.bukkit.scheduler.BukkitTask;

/**
 * Крылья ветра существуют только в раю.
 *
 * При выходе они забираются из всех слотов игрока и сохраняются в players.yml.
 * При возвращении выдаётся тот же ItemStack — вместе с прочностью, чарами и
 * любыми изменениями. Если места нет, предмет остаётся в безопасном хранилище
 * и появляется автоматически, как только освободится слот.
 */
final class ParadiseWingService implements Listener {

    private final ParadisePlugin plugin;
    private final Set<UUID> fullInventoryWarned = new HashSet<>();
    private BukkitTask watchdog;

    ParadiseWingService(final ParadisePlugin plugin) {
        this.plugin = plugin;
    }

    void enable() {
        // Страховка от любых способов перемещения и от предметов, вынутых из
        // эндер-сундука/шалкера уже после выхода из рая.
        this.watchdog = this.plugin.getServer().getScheduler().runTaskTimer(this.plugin, () -> {
            for (final Player player : this.plugin.getServer().getOnlinePlayers()) {
                synchronize(player, false);
            }
        }, 1L, 20L);
    }

    void disable() {
        if (this.watchdog != null) {
            this.watchdog.cancel();
            this.watchdog = null;
        }
        // На выключении тоже убираем крылья в отдельное хранилище. Поэтому они
        // не утекут через прокси/общий инвентарь и не потеряются при /reload.
        for (final Player player : this.plugin.getServer().getOnlinePlayers()) {
            capture(player, false);
        }
        this.plugin.players().saveNow();
    }

    private boolean isWing(final ItemStack stack) {
        return this.plugin.items().is(stack, Items.WIND_WINGS);
    }

    private boolean inParadise(final Player player) {
        return this.plugin.worlds().isParadise(player.getWorld());
    }

    private void synchronize(final Player player, final boolean notifyOutside) {
        if (!player.isOnline()) {
            return;
        }
        if (inParadise(player)) {
            restore(player);
        } else {
            // После нового входа в рай предупреждение о полном инвентаре
            // должно снова показаться, если предмет всё ещё ожидает выдачи.
            this.fullInventoryWarned.remove(player.getUniqueId());
            capture(player, notifyOutside);
        }
    }

    /** Забрать все крылья из инвентаря, брони, второй руки и курсора. */
    private boolean capture(final Player player, final boolean notify) {
        final List<ItemStack> found = removeFromPlayer(player);
        if (found.isEmpty()) {
            return false;
        }

        try {
            player.setGliding(false);
        } catch (final Throwable ignored) {
            // Некоторые сборки не разрешают менять состояние во время выхода.
        }
        this.plugin.players().addStoredWings(player.getUniqueId(), found);
        this.fullInventoryWarned.remove(player.getUniqueId());
        player.updateInventory();
        if (notify) {
            Text.action(player, "<gray>Крылья ветра остались в раю.");
        }
        return true;
    }

    private List<ItemStack> removeFromPlayer(final Player player) {
        final List<ItemStack> found = new ArrayList<>();
        final PlayerInventory inventory = player.getInventory();

        // PlayerInventory содержит хотбар, основной инвентарь, броню и вторую руку.
        for (int slot = 0; slot < inventory.getSize(); slot++) {
            final ItemStack stack = inventory.getItem(slot);
            if (!isWing(stack)) {
                continue;
            }
            found.add(stack.clone());
            inventory.setItem(slot, null);
        }

        final ItemStack cursor = player.getItemOnCursor();
        if (isWing(cursor)) {
            found.add(cursor.clone());
            player.setItemOnCursor(null);
        }
        return found;
    }

    /** Вернуть сохранённые крылья, не выбрасывая их на землю при полном инвентаре. */
    private void restore(final Player player) {
        final UUID id = player.getUniqueId();
        final List<ItemStack> stored = this.plugin.players().storedWings(id);
        if (stored.isEmpty()) {
            this.fullInventoryWarned.remove(id);
            return;
        }

        final PlayerInventory inventory = player.getInventory();
        final List<ItemStack> remaining = new ArrayList<>();
        boolean restoredAny = false;

        for (final ItemStack saved : stored) {
            final ItemStack candidate = saved.clone();
            final Map<Integer, ItemStack> leftovers = inventory.addItem(candidate);
            if (leftovers.isEmpty()) {
                restoredAny = true;
                continue;
            }

            for (final ItemStack leftover : leftovers.values()) {
                // Последняя безопасная возможность при полном основном
                // инвентаре: свободный слот нагрудника.
                if (leftover.getType() == Material.ELYTRA
                        && (inventory.getChestplate() == null || inventory.getChestplate().getType().isAir())) {
                    final ItemStack equipped = leftover.clone();
                    equipped.setAmount(1);
                    inventory.setChestplate(equipped);
                    restoredAny = true;
                    if (leftover.getAmount() > 1) {
                        final ItemStack rest = leftover.clone();
                        rest.setAmount(leftover.getAmount() - 1);
                        remaining.add(rest);
                    }
                } else {
                    remaining.add(leftover.clone());
                }
            }
        }

        if (restoredAny) {
            this.plugin.players().setStoredWings(id, remaining);
            player.updateInventory();
        }

        if (remaining.isEmpty()) {
            this.fullInventoryWarned.remove(id);
            if (restoredAny) {
                Text.action(player, "<gradient:#FFFFFF:#A5F3FC>Крылья ветра вернулись.</gradient>");
            }
            return;
        }

        if (this.fullInventoryWarned.add(id)) {
            Text.action(player, "<yellow>Освободи слот — крылья появятся сами.");
        }
    }

    private void scheduleSync(final Player player, final boolean notifyOutside) {
        this.plugin.getServer().getScheduler().runTask(this.plugin, () -> synchronize(player, notifyOutside));
    }

    // ---------------------------------------------------------------- переходы и жизнь игрока

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onTeleport(final PlayerTeleportEvent event) {
        if (event.getTo() == null || event.getFrom().getWorld() == null || event.getTo().getWorld() == null
                || event.getFrom().getWorld().getUID().equals(event.getTo().getWorld().getUID())) {
            return;
        }

        final boolean fromParadise = this.plugin.worlds().isParadise(event.getFrom().getWorld());
        final boolean toParadise = this.plugin.worlds().isParadise(event.getTo().getWorld());
        if (fromParadise && !toParadise) {
            capture(event.getPlayer(), true);
        }
        // Если телепорт отменит другой плагин или он, наоборот, ведёт в рай,
        // на следующем тике состояние всё равно будет приведено в порядок.
        scheduleSync(event.getPlayer(), fromParadise && !toParadise);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onWorldChange(final PlayerChangedWorldEvent event) {
        final boolean leftParadise = this.plugin.worlds().isParadise(event.getFrom()) && !inParadise(event.getPlayer());
        scheduleSync(event.getPlayer(), leftParadise);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(final PlayerJoinEvent event) {
        scheduleSync(event.getPlayer(), false);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onRespawn(final PlayerRespawnEvent event) {
        scheduleSync(event.getPlayer(), false);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onQuit(final PlayerQuitEvent event) {
        capture(event.getPlayer(), false);
        this.plugin.players().saveNow();
        this.fullInventoryWarned.remove(event.getPlayer().getUniqueId());
    }

    @EventHandler(priority = EventPriority.HIGHEST)
    public void onDeath(final PlayerDeathEvent event) {
        final Player player = event.getEntity();

        // Смерть тоже считается выходом из рая: крылья не должны остаться
        // лежать на земле и пропасть для игрока после возрождения.
        final List<ItemStack> found = removeFromPlayer(player);
        final Iterator<ItemStack> drops = event.getDrops().iterator();
        while (drops.hasNext()) {
            if (isWing(drops.next())) {
                drops.remove();
            }
        }
        if (!found.isEmpty()) {
            this.plugin.players().addStoredWings(player.getUniqueId(), found);
        }
    }

    // ---------------------------------------------------------------- запрет использования вне рая

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onGlide(final EntityToggleGlideEvent event) {
        if (!(event.getEntity() instanceof final Player player) || !event.isGliding() || inParadise(player)) {
            return;
        }
        if (!isWing(player.getInventory().getChestplate())) {
            return;
        }
        event.setCancelled(true);
        capture(player, true);
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onInteract(final PlayerInteractEvent event) {
        final Player player = event.getPlayer();
        if (inParadise(player) || !isWing(event.getItem())) {
            return;
        }
        event.setCancelled(true);
        capture(player, true);
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onDrop(final PlayerDropItemEvent event) {
        if (inParadise(event.getPlayer()) || !isWing(event.getItemDrop().getItemStack())) {
            return;
        }
        event.setCancelled(true);
        scheduleSync(event.getPlayer(), true);
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onPickup(final EntityPickupItemEvent event) {
        if (!(event.getEntity() instanceof final Player player) || inParadise(player)) {
            return;
        }
        final Item entity = event.getItem();
        if (!isWing(entity.getItemStack())) {
            return;
        }
        event.setCancelled(true);
        this.plugin.players().addStoredWings(player.getUniqueId(), List.of(entity.getItemStack().clone()));
        entity.remove();
        Text.action(player, "<gray>Крылья можно получить обратно только в раю.");
    }

    // Инвентарные события нужны, когда крылья достали из сундука, эндер-сундука,
    // шалкера или надели быстрым кликом. Проверка идёт после завершения события.
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onInventoryClick(final InventoryClickEvent event) {
        if (event.getWhoClicked() instanceof final Player player && !inParadise(player)) {
            scheduleSync(player, true);
        }
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onInventoryDrag(final InventoryDragEvent event) {
        if (event.getWhoClicked() instanceof final Player player && !inParadise(player)) {
            scheduleSync(player, true);
        }
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onInventoryClose(final InventoryCloseEvent event) {
        if (event.getPlayer() instanceof final Player player && !inParadise(player)) {
            scheduleSync(player, true);
        }
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onSwapHands(final PlayerSwapHandItemsEvent event) {
        if (!inParadise(event.getPlayer())) {
            scheduleSync(event.getPlayer(), true);
        }
    }
}
