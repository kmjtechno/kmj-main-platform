export declare function deviceRecoveryAction(
    platform: string | null | undefined,
    scope?: {
        deviceId?: string | null;
        pendingProjectIds?: readonly string[];
    },
): {
    href: string;
    download?: string;
    label: string;
    guidance: string;
};
