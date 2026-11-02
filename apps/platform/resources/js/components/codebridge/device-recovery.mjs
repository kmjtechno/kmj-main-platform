// Choose by the registered device OS AND exact enrollment scope, never the browser OS.
// The public Windows installer is Calibration Pro-scoped; it is not a universal
// project connector. A pending project request cannot authorize local files.
export function deviceRecoveryAction(platform, scope = {}) {
    const os =
        typeof platform === 'string' ? platform.trim().toLowerCase() : '';
    if (os === 'win32' || os === 'windows') {
        const deviceId =
            typeof scope?.deviceId === 'string' ? scope.deviceId : '';
        const pendingProjects = Array.isArray(scope?.pendingProjectIds)
            ? scope.pendingProjectIds
            : null;
        const calibrationOnly =
            deviceId === 'kmj-homeoffice-desktop-5fvjmet' &&
            pendingProjects !== null &&
            pendingProjects.length === 0;
        if (calibrationOnly) {
            return {
                href: '/install-codebridge-windows.cmd',
                download: 'KMJ-CodeBridge-Connect-Windows.cmd',
                label: 'Reconnect Calibration Pro',
                guidance:
                    'This installer is scoped only to the enrolled Home Office Calibration Pro device. It never enrolls other projects or approves a pending project assignment. Confirm the exact project grant and live heartbeat.',
            };
        }
        return {
            href: '/codebridge/pair',
            label: 'Review Windows project setup',
            guidance:
                'No project-specific Windows reconnect installer has been verified for this registration. Do not run the Calibration Pro installer for VIOSO-Clone, OmniDesk or another pending project. Pairing needs a separately verified project-scoped local agent and explicit owner approval; pending assignments alone do not grant filesystem access.',
        };
    }
    if (os === 'linux') {
        return {
            href: '/install',
            label: 'Linux / VPS setup',
            guidance:
                'On this registered Linux/VPS host, check the existing CodeBridge agent service and saved private enrollment. Use the Linux/VPS setup instructions; browser approval alone cannot start the agent.',
        };
    }
    return {
        href: '/codebridge-connect.html',
        label: 'Choose device setup',
        guidance:
            'The registered platform does not identify a supported installer. Choose setup for the actual device; do not run a connector intended for another operating system.',
    };
}
