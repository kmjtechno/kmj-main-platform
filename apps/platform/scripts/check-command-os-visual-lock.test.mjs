import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';

const read = (path) =>
    readFileSync(new URL('../' + path, import.meta.url), 'utf8');

const operator = read('resources/js/pages/operator.tsx');
const command = read('resources/js/components/operator-command-os.tsx');
const kristi = read('resources/js/components/kristi-owner-assistant.tsx');
const styles = read('resources/css/command-os.css');
const appCss = read('resources/css/app.css');
const map = read('resources/js/components/operator-workspace-map.tsx');

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

void test('visual lock retains exact signature sections and official assets', () => {
    for (const section of [
        'Super Admin',
        'Command Center',
        'Product Suite Overview',
        'Attention & Review',
        'Revenue & Growth',
        'System Health',
    ]) {
        assert.ok(command.includes(section), 'Missing section: ' + section);
    }
    assert.match(command, /<OperatorWorkspaceMap/);
    assert.match(command, /<KristiOwnerAssistant/);
    assert.match(command, /earth-orbit\.svg|kmj-os-hero/);
    assert.match(styles, /assets\/admin\/earth-orbit\.svg/);
    assert.match(kristi, /assets\/admin\/kristi-neon\.svg/);
    assert.match(appCss, /command-os\.css/);
});

void test('numbers and health indicators use authoritative data or honest missing states', () => {
    assert.match(command, /value=\{metrics\.orders\}/);
    assert.match(command, /value=\{metrics\.entitlements\}/);
    assert.match(command, /value=\{metrics\.confirmed_orders\}/);
    assert.match(command, /catalogProducts\.filter\(\(p\) => p\.is_public\)/);
    assert.match(command, /Analytics not connected/);
    assert.match(command, /No invented revenue/);
    assert.match(command, /Check/);
    assert.doesNotMatch(command, /Total Revenue.*12,64,380/);
    assert.doesNotMatch(command, /All Healthy|99\.9%/);
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

void test('navigation, responsiveness and reduced motion remain accessible', () => {
    assert.match(command, /Control|Ctrl K/);
    assert.match(
        command,
        /<Dialog\s+open=\{searchOpen\}\s+onOpenChange=\{setSearchOpen\}\s*>/,
    );
    assert.match(command, /<DialogContent/);
    assert.match(command, /<DialogTitle/);
    assert.match(command, /<DialogDescription/);
    assert.doesNotMatch(command, /onMouseDown=\{\(event\)/);
    assert.match(command, /Escape/);
    assert.match(command, /aria-label="Search owner workspaces"/);
    assert.match(command, /ref=\{carousel\}/);
    assert.match(styles, /@media\s*\(max-width:\s*1170px\)/);
    assert.match(styles, /@media\s*\(max-width:\s*720px\)/);
    assert.match(styles, /@media\s*\(prefers-reduced-motion:\s*reduce\)/);
    assert.match(map, /People & access/);
    assert.match(map, /Revenue & entitlements/);
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
