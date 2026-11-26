import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';

const read = (path) =>
    readFileSync(new URL('../' + path, import.meta.url), 'utf8');

const layout = read('resources/js/layouts/app-layout.tsx');
const shell = read('resources/js/layouts/owner-module-shell.tsx');
const command = read('resources/js/components/operator-command-os.tsx');
const shellCss = read('resources/css/owner-module-shell.css');

const ownerPages = [
    'operator-products.tsx',
    'operator-directory.tsx',
    'operator-payments.tsx',
    'operator-kslp.tsx',
    'operator-ops.tsx',
    'operator-codebridge-owner.tsx',
];

void test('all protected owner modules inherit one locked Command Center shell', () => {
    assert.match(layout, /if \(isOwner\)/);
    assert.match(layout, /<OwnerModuleShell>/);
    assert.match(shell, /data-owner-design="command-center-v1"/);
    assert.match(shell, /owner-lock owner-module-shell/);
    assert.match(shell, /<LockedBrand/);
    for (const file of ownerPages) {
        const source = read('resources/js/pages/' + file);
        assert.match(
            source,
            /owner-admin-page kmj-admin-shell|owner-product-workspace owner-admin-page kmj-admin-shell/,
        );
        assert.match(source, /owner-admin-hero kmj-admin-hero/);
        assert.match(source, /<Head title=/);
        assert.match(source, /<OperatorModuleNavigation active=/);
    }
    assert.match(command, /owner-hero/);
    assert.match(command, /owner-panel/);
});

void test('KMJ Mail renders exactly one inherited shell for owner and staff', () => {
    const appEntry = read('resources/js/app.tsx');
    const mailPage = read('resources/js/pages/mail-center.tsx');

    // Inertia mounts AppLayout for mail-center once, and its owner branch
    // renders OwnerModuleShell. A second page-level AppLayout caused the
    // duplicate branding/header/sidebar visible on the live mail screenshot.
    assert.match(appEntry, /default:\s*return AppLayout;/);
    assert.match(layout, /if \(isOwner\)/);
    assert.match(layout, /<OwnerModuleShell>/);
    assert.doesNotMatch(mailPage, /<AppLayout\b|<OwnerModuleShell\b/);
    assert.doesNotMatch(mailPage, /import AppLayout from/);
    assert.match(mailPage, /data-test="kmj-native-mail"/);
    assert.match(mailPage, /owner-admin-page kmj-admin-shell/);
    assert.match(mailPage, /<Head title="KMJ Mail/);
});

void test('one canonical Licensing Hub is shown in the owner sidebar', () => {
    const groups = shell.slice(0, shell.indexOf('export default function'));
    assert.equal((groups.match(/href: '\/operator\/kslp'/g) ?? []).length, 1);
    assert.match(groups, /label: 'KMJ Licensing Hub'/);
    assert.doesNotMatch(groups, /href: '\/developer\/apps'/);
    assert.doesNotMatch(groups, /label: 'Subscriptions & Plans'/);
    const hub = read('resources/js/pages/operator-kslp.tsx');
    assert.match(hub, /<DeveloperAppsWorkspace\s[\s\S]*?embedded/);
    assert.match(hub, /Applications, license keys &(?:amp;)? SDK/);
});

void test('products, payments, people and CodeBridge use one content width and metric scale', () => {
    for (const file of ownerPages) {
        const source = read('resources/js/pages/' + file);
        assert.doesNotMatch(source, /className="kmj-admin-shell min-h-screen/);
        assert.doesNotMatch(source, /className="mx-auto w-full max-w-6xl"/);
        assert.doesNotMatch(source, /className="mx-auto max-w-7xl"/);
        assert.match(source, /min-w-0/);
    }
    assert.match(
        shellCss,
        /\.owner-module-shell \.owner-admin-page \.owner-admin-hero h1/,
    );
    assert.match(shellCss, /--owner-surface-1:/);
    assert.match(shellCss, /--owner-line:/);
});

void test('shared CodeBridge, AI and security settings preserve customer theme', () => {
    for (const file of [
        'services/codebridge.tsx',
        'services/ai-providers.tsx',
    ]) {
        assert.match(read('resources/js/pages/' + file), /owner-admin-surface/);
    }
    for (const file of ['profile.tsx', 'security.tsx', 'appearance.tsx']) {
        assert.match(
            read('resources/js/pages/settings/' + file),
            /owner-admin-settings/,
        );
    }
    assert.match(
        shellCss,
        /\.owner-module-shell \.owner-module-content \.owner-admin-surface/,
    );
    assert.match(shellCss, /\.owner-module-shell \.owner-admin-settings/);
    assert.doesNotMatch(shellCss, /(^|\n)\s*\.owner-admin-settings\s*\{/);
    assert.doesNotMatch(shellCss, /(^|\n)\s*\.owner-admin-surface\s*\{/);
});

void test('mobile and accessible one-dashboard styles remain locked', () => {
    assert.match(shell, /aria-current=/);
    assert.match(shell, /aria-label=/);
    assert.match(shellCss, /@media \(max-width: 700px\)/);
    assert.match(shellCss, /prefers-reduced-motion: reduce/);
    assert.match(shellCss, /focus-visible/);
    assert.match(shellCss, /min-height: 42px/);
});

void test('KMJ Mail enterprise inbox controls operate on real mailbox records', () => {
    const source = read('resources/js/pages/mail-center.tsx');
    assert.match(source, /'archive', label: 'Archive'/);
    assert.match(source, /'starred', label: 'Starred'/);
    assert.match(source, /base \+ '\/messages\/manage'/);
    assert.match(source, /selectedIds\.length > 0/);
    assert.match(source, /mailbox\.total > mailbox\.page_size/);
    assert.match(source, /forwardMessage/);
    assert.match(source, /aria-label="Select all visible messages"/);
    assert.match(source, /activeSearch = q\.trim\(\)/);
    assert.match(source, /Colored\s+shortcuts search this folder/);
    assert.match(source, /No messages match your search/);
    assert.match(
        source,
        /Clear mail search and show all messages in this folder/,
    );
    assert.match(source, /Receiving not activated/);
    assert.match(source, /Incoming routing requires owner activation/);
    assert.doesNotMatch(source, /Gmail inbox synced|External inbox connected/);
});

void test('KMJ Mail AI Copilot requires consent and never sends email', () => {
    const page = read('resources/js/pages/mail-center.tsx');
    const assistant = read('resources/js/components/mail-ai-copilot.tsx');
    const routes = read('routes/workforce-mail.php');
    assert.match(page, /<MailAiCopilot/);
    assert.match(page, /onUseCompose=/);
    assert.match(page, /onUseReply=/);
    assert.match(assistant, /consent_to_ai_processing: consent/);
    assert.match(assistant, /mode === 'compose'/);
    assert.match(assistant, /selectedMessageId === null/);
    assert.match(assistant, /No verified private free AI model is connected/);
    assert.match(assistant, /AI cannot send your email/);
    assert.match(routes, /kmj-mail\.ai-generate/);
    assert.doesNotMatch(assistant, /send-external|\/mail\/send/);
});

void test('locked KMJ Mail reference uses real four-pane UI and functional controls', () => {
    const page = read('resources/js/pages/mail-center.tsx');
    const ai = read('resources/js/components/mail-ai-copilot.tsx');
    const ownerShell = read('resources/js/layouts/owner-module-shell.tsx');
    const css = read('resources/css/kmj-mail-approved.css');
    assert.match(page, /kmj-mail-approved-shell/);
    assert.match(page, /kmj-mail-hero/);
    assert.match(page, /mailMetrics\.total_messages/);
    assert.match(page, /mailMetrics\.mail_text_bytes/);
    assert.match(page, /kmj-mail-workspace-grid/);
    assert.match(page, /kmj-mail-tabs/);
    assert.match(page, /visibleItems\.map/);
    assert.match(page, /kmj-mail-sender-avatar/);
    assert.match(page, /kmj-mail-message-brand/);
    assert.match(page, /kmj-mail-floating-compose/);
    assert.match(page, /onClick=\{\(\) =>\s*submit\('send'\)\s*\}/);
    assert.match(page, /onClick=\{\(\) =>\s*submit\('draft'\)\s*\}/);
    assert.match(page, /kmj-mail-search-labels/);
    assert.match(ai, /id="kmj-ai-copilot"/);
    assert.match(ai, /Quick Actions/);
    assert.match(ai, /consent_to_ai_processing: consent/);
    assert.match(ownerShell, /owner-mail-global-search/);
    assert.match(ownerShell, /data-owner-mail=/);
    assert.match(css, /grid-template-columns: minmax\(150px, 175px\)/);
    assert.match(css, /\.kmj-mail-globe/);
    assert.match(css, /@media \(max-width: 1350px\)/);
    assert.doesNotMatch(css, /@media \(max-width: 1500px\)/);
    assert.doesNotMatch(page, /1,248|50 GB|36 Team Recipients/);
});

void test('mail folder reader never substitutes Sent previews and AI is opt-in', () => {
    const page = read('resources/js/pages/mail-center.tsx');
    const ai = read('resources/js/components/mail-ai-copilot.tsx');
    const controller = read('app/Http/Controllers/NativeMailController.php');
    assert.doesNotMatch(
        page,
        /latestSent|recentSent|kmj-mail-recent-sent-reader/,
    );
    assert.match(page, /Inbox is clear/);
    assert.match(page, /View Sent/);
    assert.match(controller, /'recentSent' => null/);
    assert.match(ai, /\[expanded, setExpanded\] = useState\(false\)/);
    assert.match(ai, /aria-expanded=\{expanded\}/);
    assert.match(ai, /hidden=\{!expanded\}/);
    assert.match(ai, /consent_to_ai_processing: consent/);
});

void test('focused mail composer preserves recipients, removes old thread underlay and explains send blockers', () => {
    const page = read('resources/js/pages/mail-center.tsx');
    assert.doesNotMatch(page, /kmj-mail-compose-underlay/);
    assert.match(page, /data-compose-focus=/);
    assert.match(page, /sendBlockReason/);
    assert.match(page, /aria-describedby="kmj-mail-send-status"/);
    assert.match(page, /if \(view !== 'compose'\) startCompose\(\)/);
    assert.match(page, /Close without saving/);
});
