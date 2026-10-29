export declare function createSingleFlightGate(): {
    enter(): boolean;
    leave(): void;
    isBusy(): boolean;
};

export declare function normalizeRetryAfter(
    value: unknown,
    fallback?: number,
): number;
export declare function createCloudCooldown(now?: () => number): {
    remaining(): number;
    defer(seconds: unknown): void;
    subscribe(listener: () => void): () => void;
};
