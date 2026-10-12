import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const servicePage = readFileSync(
    'resources/js/pages/services/codebridge.tsx',
    'utf8',
);

void test('primary VS Code action uses credential-free native install link', () => {
    const start = servicePage.indexOf('<div className="flex flex-wrap gap-2">');
    const end = servicePage.indexOf('</div>', start);
    assert.ok(start >= 0 && end > start);
    const primaryActions = servicePage.slice(start, end);
    assert.match(
        primaryActions,
        /href=\{vscodeInstallUrl\(service\.endpoint\)\}/,
    );
    assert.doesNotMatch(primaryActions, /href=\{VSCODE_COPILOT_SETUP_URL\}/);
    assert.match(servicePage, /VS Code opens a confirmation dialog/);
});

void test('Linux bootstrap is downloaded for inspection, not piped to root', () => {
    assert.match(
        servicePage,
        /href="\/install"\s+download="KMJ-CodeBridge-VPS\.sh"/,
    );
    assert.match(servicePage, /sudo bash KMJ-CodeBridge-VPS\.sh/);
    assert.doesNotMatch(servicePage, /curl[^\n]*\|\s*sudo\s*bash/);
    assert.match(
        servicePage,
        /Download and inspect the pinned bootstrap first/,
    );
});

void test('Claude Desktop and multi-chat guidance stays hosted OAuth only', () => {
    assert.match(servicePage, /Claude Desktop \/ Claude web/);
    assert.match(servicePage, /Managed MCP/);
    assert.match(servicePage, /Copy Claude MCP URL/);
    assert.match(servicePage, /navigator\.clipboard\.writeText\(service\.endpoint\)/);
    assert.match(servicePage, /Multiple AI chats \/ automatic updates/);
    assert.match(servicePage, /cannot\s+be silently updated by CodeBridge/);
    assert.doesNotMatch(servicePage, /claude_desktop_config\.json/);
});
