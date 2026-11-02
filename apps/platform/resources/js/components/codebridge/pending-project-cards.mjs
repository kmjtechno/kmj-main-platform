// Pending project requests must never inherit registered device actions.
// A request is not another credential, connected agent or verified grant.
export function pendingProjectCards(devices) {
    if (!Array.isArray(devices)) return [];
    const requests = [];
    const seen = new Set();
    for (const device of devices) {
        if (typeof device?.id !== 'string' || !device.id) continue;
        for (const pending of Array.isArray(device.pending_projects)
            ? device.pending_projects
            : []) {
            if (!pending || pending.status !== 'pending_local_setup' ||
                typeof pending.id !== 'string' || !pending.id) continue;
            const key = device.id + ':' + pending.id;
            if (seen.has(key)) continue;
            seen.add(key);
            requests.push({
                key,
                sourceDeviceId: device.id,
                sourceDeviceName:
                    typeof device.name === 'string' && device.name
                        ? device.name
                        : device.id,
                projectId: pending.id,
                projectName:
                    typeof pending.name === 'string' && pending.name
                        ? pending.name
                        : pending.id,
                status: 'pending_local_setup',
                registration: 'not_registered',
                connectionStatus: 'not_verified',
            });
        }
    }
    return requests;
}
