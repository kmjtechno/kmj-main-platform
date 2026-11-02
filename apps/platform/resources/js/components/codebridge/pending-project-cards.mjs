// Pending requests never inherit registered device actions.
// A request is not another credential, connected agent or verified grant.
export function pendingProjectCards(devices) {
    if (!Array.isArray(devices)) return [];

    const requests = [];
    const seen = new Set();

    for (const device of devices) {
        if (typeof device?.id !== 'string' || !device.id) continue;

        const pendingProjects = Array.isArray(device.pending_projects)
            ? device.pending_projects
            : [];
        for (const pending of pendingProjects) {
            if (pending?.status !== 'pending_local_setup') continue;
            if (typeof pending.id !== 'string' || !pending.id) continue;

            const key = device.id + ':' + pending.id;
            if (seen.has(key)) continue;
            seen.add(key);

            const sourceDeviceName =
                typeof device.name === 'string' && device.name
                    ? device.name
                    : device.id;
            const projectName =
                typeof pending.name === 'string' && pending.name
                    ? pending.name
                    : pending.id;
            requests.push({
                key,
                sourceDeviceId: device.id,
                sourceDeviceName,
                projectId: pending.id,
                projectName,
                status: 'pending_local_setup',
                registration: 'not_registered',
                connectionStatus: 'not_verified',
            });
        }
    }

    return requests;
}
