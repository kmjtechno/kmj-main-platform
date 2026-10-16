/** Types for the standalone KSLP first-use JS module.
 *  Device registration never grants signed commercial entitlement.
 */
export type KslpPlatform =
    | 'windows'
    | 'linux'
    | 'macos'
    | 'android'
    | 'ios'
    | 'other';

export interface KslpFirstUseReceipt {
    readonly activationId: string;
    readonly productCode: string;
    readonly deviceRegistered: true;
    readonly signedLeaseIssued: false;
    readonly grantsEntitlement: false;
}

export interface KslpFirstUseOptions {
    licenseKey: string;
    productCode: string;
    devicePublicKey: Uint8Array;
    machineHash: string;
    /** Stable matching Ed25519 signer backed by OS keystore; never inline private keys. */
    sign(message: Uint8Array): Uint8Array | Promise<Uint8Array>;
    metadataConsent?: boolean;
    platform?: KslpPlatform | null;
    appVersion?: string | null;
    /** For offline test fixtures. Real integrations should not override this. */
    request?: (
        url: string,
        payload: Record<string, unknown>,
    ) => Promise<Record<string, unknown>>;
}

export class KslpFirstUseError extends Error {
    readonly code: string;
    constructor(code: string);
}

export function postKslpFirstUse(
    url: string,
    payload: Record<string, unknown>,
): Promise<Record<string, unknown>>;

export function registerKslpFirstUseDevice(
    options: KslpFirstUseOptions,
): Promise<KslpFirstUseReceipt>;
