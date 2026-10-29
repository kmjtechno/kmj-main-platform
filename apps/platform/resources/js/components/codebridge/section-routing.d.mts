export type CodeBridgeSectionName =
    | 'overview'
    | 'devices'
    | 'setup'
    | 'usage'
    | 'billing'
    | 'clients'
    | 'settings';
export declare const CODEBRIDGE_SECTIONS: readonly CodeBridgeSectionName[];
export declare function codeBridgeSectionFromHash(
    hash: string | null | undefined,
): CodeBridgeSectionName;
export declare function codeBridgeAnchorFromHash(
    hash: string | null | undefined,
): string | null;
