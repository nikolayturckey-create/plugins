package ru.projecterror.kitacat;

public enum KitaEmotion {
    HAPPY,
    SAD,
    WAITING,
    TRUST,
    LONELY,
    SLEEPY;

    public static KitaEmotion fromString(String value) {
        if (value == null || value.isBlank()) {
            return TRUST;
        }
        try {
            return KitaEmotion.valueOf(value.trim().toUpperCase());
        } catch (IllegalArgumentException ignored) {
            return TRUST;
        }
    }
}
