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
