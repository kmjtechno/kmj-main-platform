// Choose by the registered device OS, never the browser's OS or architecture.
export function deviceRecoveryAction(platform) {
    const os =
        typeof platform === 'string' ? platform.trim().toLowerCase() : '';
    if (os === 'win32' || os === 'windows') {
        return {
            href: '/install-codebridge-windows.cmd',
            download: 'KMJ-CodeBridge-Connect-Windows.cmd',
            label: 'Reconnect on Windows',
            guidance:
                'Run the Windows connector on this registered Windows device. Reuse its saved private enrollment when available; approve a new code only when a new grant is needed.',
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
