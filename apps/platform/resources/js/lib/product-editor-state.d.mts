export declare function withNewProductName<T extends { name: string; slug: string }>(
    current: T,
    name: string,
    slugEdited?: boolean,
): T;

export declare function withProductLifecycle<
    T extends { lifecycle: string; purchase_enabled: boolean },
>(current: T, lifecycle: string): T;
