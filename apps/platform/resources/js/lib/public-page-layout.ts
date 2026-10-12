// Only explicitly public, full-bleed marketing/legal pages are exempt from
// the authenticated application shell. Do not use URL, login state, or a
// broad prefix: future authenticated pages must retain their own controls.
const standalonePublicPages = new Set([
    'welcome',
    'company',
    'contact',
    'capabilities',
    'trust',
    'public-page',
    'products/index',
    'products/show',
    'products/codebridge/terms',
    'products/codebridge/privacy',
    'products/codebridge/support',
    'legal/index',
    'legal/terms',
    'legal/privacy',
    'legal/refund-policy',
    'legal/acceptable-use',
    'legal/cookie-policy',
]);

export function isPublicMarketingPage(name: string): boolean {
    return standalonePublicPages.has(name);
}
