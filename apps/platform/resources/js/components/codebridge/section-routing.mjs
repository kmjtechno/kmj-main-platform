// Deep links into the single canonical CodeBridge Control Center
// (/services/kmj-codebridge). Only whitelisted section names or the stable
// anchors used by other KMJ pages are honoured; anything else stays on the
// overview so a crafted hash can never select unknown UI state.
export const CODEBRIDGE_SECTIONS = [
    'overview',
    'devices',
    'setup',
    'usage',
    'billing',
    'clients',
    'settings',
];

const ANCHOR_SECTION = {
    'codebridge-device-control': 'devices',
    'codebridge-clients': 'clients',
};

export function codeBridgeSectionFromHash(hash) {
    if (typeof hash !== 'string') return 'overview';
    const name = hash.replace(/^#/, '').trim().toLowerCase();
    if (Object.hasOwn(ANCHOR_SECTION, name)) return ANCHOR_SECTION[name];
    return CODEBRIDGE_SECTIONS.includes(name) ? name : 'overview';
}

// The element id to scroll to once the section has rendered, or null when the
// hash only names a section (the section header stays at the top).
export function codeBridgeAnchorFromHash(hash) {
    if (typeof hash !== 'string') return null;
    const name = hash.replace(/^#/, '').trim().toLowerCase();
    return Object.hasOwn(ANCHOR_SECTION, name) ? name : null;
}

// True when the hash is a navigation instruction (empty hash and #overview
// return to the overview; whitelisted names/anchors select their section).
// Unknown hashes are not instructions, so a crafted hash changes nothing.
export function codeBridgeHashIsNavigable(hash) {
    if (typeof hash !== 'string') return false;
    const name = hash.replace(/^#/, '').trim().toLowerCase();
    return (
        name === '' ||
        Object.hasOwn(ANCHOR_SECTION, name) ||
        CODEBRIDGE_SECTIONS.includes(name)
    );
}
