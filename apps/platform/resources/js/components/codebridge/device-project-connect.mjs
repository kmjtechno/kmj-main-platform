import { deviceRecoveryAction } from './device-recovery.mjs';

// Client-side navigation ONLY. Existing tenant-scoped server data is the
// source of selectable registered device/project grants. This helper cannot
// grant permissions, retrieve enrollment secrets or start remote agents.
export function deviceProjectConnectPlan(device, projectId) {
    if (
        !device ||
        typeof device.id !== 'string' ||
        !/^[A-Za-z0-9_-]{1,64}$/.test(device.id) ||
        !Array.isArray(device.projects) ||
        typeof projectId !== 'string' ||
        !/^[a-z0-9][a-z0-9_-]{0,63}$/.test(projectId)
    ) {
        return null;
    }
    const project = device.projects.find(
        (item) =>
            item && item.id === projectId && typeof item.name === 'string',
    );
    if (!project) return null; // Pending requests are NOT active grants.

    const action = deviceRecoveryAction(device.platform, {
        deviceId: device.id,
        pendingProjectIds: Array.isArray(device.pending_projects)
            ? device.pending_projects.map((item) => item.id)
            : [],
    });
    if (
        !action ||
        ![
            '/install',
            '/codebridge/pair',
            '/codebridge-connect.html',
            '/install-codebridge-windows.cmd',
        ].includes(action.href)
    )
        return null;

    const unredeemed = device.pairing_state === 'approved_unredeemed';
    return {
        href: action.href,
        download: action.download ?? undefined,
        label: unredeemed ? 'Review existing enrollment' : action.label,
        guidance: unredeemed
            ? 'Approval has not been redeemed by this exact agent. Check its existing private enrollment before requesting a fresh code. This action does not make it online.'
            : action.guidance,
        deviceId: device.id,
        projectId: project.id,
        proof: 'No verified gateway heartbeat is available in this dashboard.',
    };
}
