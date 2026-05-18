package ru.projecterror.kitacat;

import org.bukkit.configuration.file.FileConfiguration;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.plugin.java.JavaPlugin;

import java.io.File;
import java.io.IOException;
import java.util.logging.Level;

public final class KitaCatPlugin extends JavaPlugin {
    private File dataFile;
    private FileConfiguration dataConfig;
    private KitaManager kitaManager;
    private KitaMomentManager momentManager;
    private KitaMoodManager moodManager;
    private KitaGiftManager giftManager;
    private KitaDangerManager dangerManager;
    private KitaSleepManager sleepManager;

    @Override
    public void onEnable() {
        saveDefaultConfig();
        loadData();

        this.kitaManager = new KitaManager(this);
        this.moodManager = new KitaMoodManager(this, kitaManager);
        this.momentManager = new KitaMomentManager(this, kitaManager);
        this.giftManager = new KitaGiftManager(this, kitaManager);
        this.dangerManager = new KitaDangerManager(this, kitaManager, moodManager);
        this.sleepManager = new KitaSleepManager(this, kitaManager, moodManager, dangerManager);

        KitaCommand command = new KitaCommand(this, kitaManager, moodManager);
        if (getCommand("kita") != null) {
            getCommand("kita").setExecutor(command);
            getCommand("kita").setTabCompleter(command);
        }

        getServer().getPluginManager().registerEvents(new KitaListener(this, kitaManager), this);
        getServer().getPluginManager().registerEvents(new OwnerJoinLeaveListener(kitaManager, moodManager), this);

        getServer().getScheduler().runTask(this, kitaManager::restoreOrCreateKita);
        kitaManager.startTasks();
        moodManager.start();
        momentManager.start();
        giftManager.start();
        dangerManager.start();
        sleepManager.start();
    }

    @Override
    public void onDisable() {
        if (momentManager != null) {
            momentManager.stop();
        }
        if (moodManager != null) {
            moodManager.stop();
        }
        if (giftManager != null) {
            giftManager.stop();
        }
        if (dangerManager != null) {
            dangerManager.stop();
        }
        if (sleepManager != null) {
            sleepManager.stop();
        }
        if (kitaManager != null) {
            kitaManager.shutdownSave();
        }
        saveData();
    }

    public void reloadPluginConfig() {
        reloadConfig();
        if (momentManager != null) {
            momentManager.restart();
        }
        if (moodManager != null) {
            moodManager.restart();
        }
        if (giftManager != null) {
            giftManager.restart();
        }
        if (dangerManager != null) {
            dangerManager.restart();
        }
        if (sleepManager != null) {
            sleepManager.restart();
        }
    }

    public FileConfiguration getDataConfig() {
        return dataConfig;
    }

    public KitaMoodManager getMoodManager() {
        return moodManager;
    }

    public void saveData() {
        if (dataConfig == null || dataFile == null) {
            return;
        }
        try {
            dataConfig.save(dataFile);
        } catch (IOException exception) {
            getLogger().log(Level.WARNING, "Не удалось сохранить data.yml", exception);
        }
    }

    private void loadData() {
        if (!getDataFolder().exists() && !getDataFolder().mkdirs()) {
            getLogger().warning("Не удалось создать папку плагина.");
        }
        dataFile = new File(getDataFolder(), "data.yml");
        if (!dataFile.exists()) {
            saveResource("data.yml", false);
        }
        dataConfig = YamlConfiguration.loadConfiguration(dataFile);
        addDataDefaults();
        saveData();
    }

    private void addDataDefaults() {
        dataConfig.addDefault("kita.uuid", "");
        dataConfig.addDefault("kita.spawned", false);
        dataConfig.addDefault("kita.sitting", false);
        dataConfig.addDefault("kita.following", true);
        dataConfig.addDefault("kita.last-location.world", getConfig().getString("kita.world", "world"));
        dataConfig.addDefault("kita.last-location.x", 0.0);
        dataConfig.addDefault("kita.last-location.y", 80.0);
        dataConfig.addDefault("kita.last-location.z", 0.0);
        dataConfig.addDefault("kita.last-location.yaw", 0.0);
        dataConfig.addDefault("kita.last-location.pitch", 0.0);
        dataConfig.options().copyDefaults(true);
    }
}
