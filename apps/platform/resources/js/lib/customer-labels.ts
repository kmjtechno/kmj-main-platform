/**
 * Plain words for the codes stored in licensing and access records. Display
 * only: authorization always uses the stored values on the server.
 */
const productNames: Record<string, string> = {
    KMJ_CLOUDOS: 'KMJ CloudOS',
    KMJ_CODEBRIDGE: 'KMJ CodeBridge',
    KMJ_OMNIDESK: 'KMJ OmniDesk',
    KMJ_CINECORE: 'KMJ CineCore',
    KMJ_CALIBRATION_PRO: 'KMJ Calibration Pro',
};

const licenseStates: Record<string, string> = {
    ACTIVE: 'Active',
    RENEWAL_DUE: 'Expires soon',
    GRACE: 'Expired · grace period',
    NOT_STARTED: 'Not started yet',
    REVOKED: 'Revoked',
    RESTRICTED: 'Not usable',
};

function words(value: string): string {
    return value
        .split(/[._\-:]+/)
        .filter(Boolean)
        .map(
            (part) =>
                part.charAt(0).toUpperCase() + part.slice(1).toLowerCase(),
        )
        .join(' ');
}

export function productLabel(code: string): string {
    return productNames[code] ?? words(code).replace(/^Kmj\b/, 'KMJ');
}

export function planLabel(plan: string): string {
    return plan === 'custom_oem' ? 'Custom / OEM' : words(plan);
}

export function licenseStateLabel(state: string): string {
    return licenseStates[state] ?? 'Unknown';
}

/** States in which the license record is inside its valid or grace window. */
export function isUsableLicenseState(state: string): boolean {
    return ['ACTIVE', 'RENEWAL_DUE', 'GRACE'].includes(state);
}

export function accessStatusLabel(status: string): string {
    return status === 'active' ? 'Switched on' : words(status);
}

export function featureLabel(capability: string): string {
    return words(capability)
        .replace(/\bCodebridge\b/, 'CodeBridge')
        .replace(/\bCloudos\b/, 'CloudOS')
        .replace(/\bOmnidesk\b/, 'OmniDesk')
        .replace(/\bCinecore\b/, 'CineCore');
}
