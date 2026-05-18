package ru.projecterror.kitacat;

public enum KitaMood {
    HAPPY("радостная"),
    CALM("спокойная"),
    LONELY("скучает"),
    SLEEPY("сонная"),
    SCARED("напугана");

    private final String displayName;

    KitaMood(String displayName) {
        this.displayName = displayName;
    }

    public String getDisplayName() {
        return displayName;
    }
}
