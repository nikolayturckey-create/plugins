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

    @Override
    public void onEnable() {
        saveDefaultConfig();
        loadData();

        this.kitaManager = new KitaManager(this);
        this.momentManager = new KitaMomentManager(this, kitaManager);

        KitaCommand command = new KitaCommand(this, kitaManager, momentManager);
        if (getCommand("kita") != null) {
            getCommand("kita").setExecutor(command);
            getCommand("kita").setTabCompleter(command);
        }

        getServer().getPluginManager().registerEvents(new KitaListener(this, kitaManager), this);

        getServer().getScheduler().runTask(this, kitaManager::restoreOrCreateKita);
        kitaManager.startTasks();
        momentManager.start();
    }

    @Override
    public void onDisable() {
        if (momentManager != null) {
            momentManager.stop();
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
    }

    public FileConfiguration getDataConfig() {
        return dataConfig;
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
