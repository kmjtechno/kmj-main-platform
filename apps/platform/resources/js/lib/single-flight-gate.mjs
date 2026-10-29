// Synchronous, instance-scoped gate for duplicate user actions. The caller
// always releases it in finally; no timer, persistence or network side effect.
export function createSingleFlightGate() {
    let locked = false;
    return {
        enter() {
            if (locked) return false;
            locked = true;
            return true;
        },
        leave() {
            locked = false;
        },
        isBusy() {
            return locked;
        },
    };
}

export function normalizeRetryAfter(value, fallback = 60) {
    if (
        (typeof value !== 'number' &&
            !(typeof value === 'string' && /^\d+$/.test(value))) ||
        !Number.isFinite(Number(value)) ||
        Number(value) <= 0
    )
        return fallback;
    return Math.min(86400, Math.ceil(Number(value)));
}

// One shared countdown for text generation. Timers only notify UI subscribers;
// they never retry a request, change providers or persist product content.
export function createCloudCooldown(now = Date.now) {
    let until = 0;
    let timer;
    const listeners = new Set();
    const remaining = () => Math.max(0, Math.ceil((until - now()) / 1000));
    const stop = () => {
        if (timer !== undefined) clearInterval(timer);
        timer = undefined;
    };
    const notify = () => {
        for (const listener of listeners) listener();
    };
    const start = () => {
        if (timer !== undefined || listeners.size === 0 || remaining() === 0)
            return;
        timer = setInterval(() => {
            notify();
            if (remaining() === 0) stop();
        }, 1000);
    };
    return {
        remaining,
        defer(seconds) {
            until = Math.max(
                until,
                now() + normalizeRetryAfter(seconds) * 1000,
            );
            start();
            notify();
        },
        subscribe(listener) {
            listeners.add(listener);
            start();
            return () => {
                listeners.delete(listener);
                if (listeners.size === 0) stop();
            };
        },
    };
}
