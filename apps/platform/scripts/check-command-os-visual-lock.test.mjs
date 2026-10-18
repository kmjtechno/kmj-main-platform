import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';

const read = (path) =>
    readFileSync(new URL('../' + path, import.meta.url), 'utf8');

const operator = read('resources/js/pages/operator.tsx');
const command = read('resources/js/components/operator-command-os.tsx');
const kristi = read('resources/js/components/kristi-owner-assistant.tsx');

void test('locked owner command center is rendered only in the guarded operator route', () => {
    assert.match(operator, /<OperatorCommandOs/);
    assert.match(operator, /<OperatorControlOverview/);
    assert.match(operator, /href="\/operator\/products"/);
    assert.match(operator, /<Head title="KMJ Enterprise Command OS/);
    assert.match(operator, /id="commercial-orders"/);
    assert.match(operator, /ManualPaymentConfirmation/);
    assert.match(operator, /order\.fulfillment_state ===/);
    assert.doesNotMatch(command, /router\.post\(/);
});

void test('visual lock retains signature sections and generated production assets', () => {
    for (const section of [
        'Super Admin',
        'Command Center',
        'Product Suite Overview',
        'Revenue & Growth',
        'Recent Orders',
        'System Health',
        'Recent Platform Activity',
        'Quick Tools & Actions',
    ])
        assert.ok(command.includes(section), section);
    assert.match(command, /<LockedBrand/);
    assert.match(command, /<KristiOwnerAssistant/);
    assert.match(command, /assets\/locked\/owner-earth\.webp/);
    assert.match(kristi, /assets\/locked\/kristi-owner\.webp/);
    assert.ok(
        read('resources/css/owner-lock.css').includes('grid-template-columns'),
    );
});
void test('numbers and health indicators use authoritative data or honest missing states', () => {
    for (const field of [
        'metrics.users',
        'metrics.entitlements',
        'metrics.orders',
        'metrics.confirmed_orders',
    ])
        assert.ok(command.includes(field));
    assert.match(command, /o.status === 'confirmed'/);
    assert.match(command, /o.currency === 'INR'/);
    assert.match(command, /Not verified/);
    // The KPI is an all-orders backend aggregate; the chart is a recent snapshot.
    assert.match(command, /metrics\.confirmed_inr_revenue_minor/);
    assert.match(command, /All confirmed INR orders/);
    assert.match(command, /Last 20 orders, confirmed INR only/);
    assert.doesNotMatch(command, /12,64,380|All Healthy|99\.9%/);
});

void test('Kristi is a clearly labeled guided assistant with opt-in voice', () => {
    assert.match(kristi, /Guided mode/);
    assert.match(kristi, /live AI reasoning is not connected/);
    assert.match(kristi, /SpeechRecognition/);
    assert.match(kristi, /session\.start\(\)/);
    assert.match(kristi, /Start voice dictation/);
    assert.match(kristi, /Stop voice dictation/);
    assert.match(kristi, /Read-only guidance/);
    assert.match(kristi, /maxLength=\{400\}/);
    assert.match(kristi, /role="log"/);
    assert.doesNotMatch(kristi, /router\.post\(|fetch\(/);
});

void test('navigation and palette remain keyboard accessible', () => {
    assert.match(command, /<Dialog[\s\S]*open=\{searchOpen\}/);
    for (const name of [
        'DialogContent',
        'DialogTitle',
        'DialogDescription',
        'Escape',
        'Search owner workspaces and catalog products',
    ])
        assert.ok(command.includes(name));
    const responsive = read('resources/css/owner-lock.css');
    assert.match(responsive, /@media\s*\(max-width:\s*700px\)/);
    assert.match(responsive, /prefers-reduced-motion/);
});
void test('product carousel respects reduced motion in both directions', () => {
    assert.match(command, /function scrollProducts\(distance: number\)/);
    assert.match(command, /prefers-reduced-motion: reduce/);
    assert.match(command, /\? 'auto'\s*:\s*'smooth'/);
    assert.match(command, /scrollProducts\(-260\)/);
    assert.match(command, /scrollProducts\(260\)/);
});
void test('owner palette searches only loaded catalog products and authorized workspaces', () => {
    assert.match(command, /catalogProducts[\s\S]*?\.filter\(/);
    assert.match(command, /product.name \+ ' ' \+ product.slug/);
    assert.match(command, /category: 'Catalog product'/);
    assert.match(command, /category: 'Workspace'/);
    assert.match(command, /slice\(0, 20\)/);
    assert.doesNotMatch(command, /fetch\(|router.post\(/);
});

void test('Kristi chat updates never scroll the entire owner dashboard', () => {
    assert.match(kristi, /const chatHistory = useRef/);
    assert.match(kristi, /ref=\{chatHistory\}/);
    assert.match(kristi, /history\.scrollTo\(/);
    assert.match(kristi, /prefers-reduced-motion: reduce/);
    assert.doesNotMatch(kristi, /scrollIntoView\(/);
});

void test('Kristi Hindi voice selection changes guided answer language without remote AI', () => {
    assert.match(kristi, /voiceLanguage/);
    assert.match(kristi, /session\.lang = voiceLanguage/);
    assert.match(
        kristi,
        /guidance\(\s*clean,\s*counts,\s*voiceLanguage,?\s*\)/,
    );
    assert.match(kristi, /भुगतान की पुष्टि/);
    assert.match(kristi, /जनरेटिव AI अभी कनेक्ट नहीं है/);
    assert.doesNotMatch(kristi, /fetch\(|router\.post\(/);
});

void test('Kristi microphone requires explicit informed consent before browser speech starts', () => {
    assert.match(
        kristi,
        /const \[speechConsent, setSpeechConsent\] = useState\(false\)/,
    );
    assert.match(kristi, /if \(!speechConsent\)\s*\{/);
    assert.match(kristi, /checked=\{speechConsent\}/);
    assert.match(kristi, /setSpeechConsent\(event\.target\.checked\)/);
    assert.match(
        kristi,
        /browser speech recognition may send\s+microphone audio/,
    );
    assert.ok(
        kristi.indexOf('if (!speechConsent)') <
            kristi.indexOf('session.start()'),
    );
    assert.match(kristi, /disabled=\{listening\}/);
    assert.match(kristi, /setDraft\(transcript\.slice\(0, 400\)\)/);
});

void test('owner badge derives from authenticated user and catalog art fails closed', () => {
    assert.match(command, /auth\.user\?\.name\?\.trim\(\)/);
    assert.match(command, /const initials =/);
    assert.match(command, /\{initials\}/);
    assert.doesNotMatch(command, /owner-initials">NK/);
    assert.doesNotMatch(
        command,
        /auth\.user\?\.name \|\| 'Narendra Singh Kushwah'/,
    );
    assert.match(command, /owner-product-art-unavailable/);
    assert.doesNotMatch(command, /art\[p\.slug\] \|\| 'cloudos'/);
});

void test('browser QA decodes off-screen lazy carousel images before checking failed assets', () => {
    const browser = read('scripts/browser-preview-verify.mjs');
    assert.match(browser, /image\.loading = 'eager'/);
    assert.match(browser, /Promise\.allSettled\(/);
    assert.match(browser, /image\.decode\(\)/);
    assert.match(browser, /decoded\[index\]\?\.status === 'rejected'/);
    assert.match(browser, /image\.naturalWidth === 0/);
});
