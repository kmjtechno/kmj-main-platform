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
    remaining(this: void): number;
    defer(this: void, seconds: unknown): void;
    subscribe(this: void, listener: () => void): () => void;
};
