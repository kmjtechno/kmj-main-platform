// Owner Product Studio dependent fields must update in one React state
// transition. Separate Inertia setData calls in one event may be batched.
export function withNewProductName(current, name, slugEdited = false) {
    return {
        ...current,
        name,
        slug: slugEdited
            ? current.slug
            : name
                  .toLowerCase()
                  .normalize('NFKD')
                  .replace(/[\u0300-\u036f]/g, '')
                  .replace(/[^a-z0-9]+/g, '-')
                  .replace(/^-|-$/g, '')
                  .slice(0, 96),
    };
}

// Preview, beta, research, planned and retired are never purchasable.
// Returning to Available must not silently turn purchasing back on.
export function withProductLifecycle(current, lifecycle) {
    return {
        ...current,
        lifecycle,
        purchase_enabled:
            lifecycle === 'available' ? current.purchase_enabled : false,
    };
}
