// The owner tier uses a machine integer ceiling to avoid an arbitrary low
// enrollment cap. It is neither a measured device capacity nor "unlimited".
export const OWNER_POLICY_DEVICE_CEILING = 2147483647;

export function codeBridgeDeviceQuotaDisplay(
    plan: string | null,
    managedDevices: number,
    deviceLimit: number | null,
): { value: string; detail: string; registrationHint: string } {
    if (plan === 'owner' && deviceLimit === OWNER_POLICY_DEVICE_CEILING) {
        return {
            value: `${managedDevices} registered · Owner tier`,
            detail: 'Owner plan technical ceiling; not live or executable capacity',
            registrationHint:
                'Owner-tier technical ceiling (not a live device limit)',
        };
    }

    return {
        value:
            deviceLimit === null
                ? 'Not reported'
                : `${managedDevices} / ${deviceLimit}`,
        detail: 'Known registrations against the licensed limit',
        registrationHint:
            deviceLimit === null
                ? 'Plan limit not reported'
                : `Plan limit: ${deviceLimit}`,
    };
}
