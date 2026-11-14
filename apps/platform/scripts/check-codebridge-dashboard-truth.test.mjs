import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { readSourceText } from './source-text.mjs';
import { deviceProjectConnectPlan } from '../resources/js/components/codebridge/device-project-connect.mjs';

const ui = readSourceText('resources/js/pages/services/codebridge.tsx');
// Device cards are rendered by the Device Control Center component (PR #377);
// device-health truth rules apply to the page and the component together.
const deviceCenter = readSourceText(
    'resources/js/components/codebridge/device-control-center.tsx',
);
const deviceUi = `${ui}\n${deviceCenter}`;
const directory = readFileSync(
    'app/Services/Licensing/CodeBridge/CodeBridgeCustomerDeviceDirectory.php',
    'utf8',
);
const enrollment = readSourceText(
    'app/Services/Licensing/CodeBridge/CodeBridgeDeviceEnrollmentService.php',
);
const routes = readFileSync('routes/web.php', 'utf8');

void test('green entitlement badge and owner plan ceiling cannot imply device online', () => {
    assert.match(ui, /Entitlement: \{entitlement\.status\}/);
    assert.match(ui, /codeBridgeDeviceQuotaDisplay/);
    assert.match(ui, /\.registrationHint/);
    assert.doesNotMatch(ui, />\s*\{entitlement\.status\}\s*<\/span>/);
    assert.doesNotMatch(ui, /'Limit ' \+ service\.device_limit/);
});

void test('dashboard never invents online device presence from registration', () => {
    assert.match(directory, /'connection_status' => 'not_verified'/);
    assert.match(deviceCenter, /Online status: Not verified/);
    assert.match(deviceCenter, /Live connection has not been verified/);
    assert.match(deviceCenter, /Registered · Live status unknown/);
    assert.doesNotMatch(deviceUi, /connection_status === 'online'/);
    assert.doesNotMatch(deviceUi, />\s*Online\s*</);
});

void test('approved-but-unredeemed device cannot masquerade as a successfully paired agent', () => {
    assert.match(
        directory,
        /'pairing_state' => CodeBridgeDeviceEnrollmentService::pairingState\(/,
    );
    assert.match(enrollment, /'approved_unredeemed'/);
    assert.match(enrollment, /'approval_expired'/);
    assert.match(enrollment, /'redeemed'/);
    assert.match(deviceCenter, /Approved · Not redeemed/);
    assert.match(deviceCenter, /Pairing redemption receipt missing/);
    assert.match(deviceCenter, /This pairing record has no redemption receipt/);
    assert.match(deviceCenter, /recent\s+password confirmation required/);
    assert.match(deviceCenter, /gateway heartbeat is verified/);
    assert.match(deviceCenter, /connection_status: 'not_verified'/);
});

void test('permissions must be backed by actual server-authorized scope', () => {
    assert.match(ui, /service\.permissions\.map\(\(permission\)/);
    assert.match(ui, /No permissions reported/);
    assert.doesNotMatch(ui, /\['read', 'write', 'execute'\]/);
});

void test('device cards are searchable without changing tenant authorization', () => {
    assert.match(
        ui,
        /<DeviceControlCenter[\s\S]*tenantId=\{organization\.id\}/,
    );
    assert.match(deviceCenter, /visibleDevices\.map\(\(device\)/);
    assert.match(deviceCenter, /Search device, OS, project or ID/);
    assert.match(
        routes,
        /\$deviceDirectory->forTenant\(\(string\) \$organization\['id'\], time\(\)\)/,
    );
    assert.match(directory, /->where\('c\.tenant_id', \$tenantId\)/);
});

void test('OAuth grants are not mislabeled as live IDE connections', () => {
    assert.match(ui, /authorized refresh sessions/);
    assert.match(ui, /Last token activity/);
    assert.match(ui, /authorized OAuth refresh grants/);
    assert.doesNotMatch(ui, /\} active\s*<\/span>/);
});

void test('revocation requires confirmation and prevents duplicate clicks', () => {
    assert.match(ui, /window\.confirm\(/);
    assert.match(ui, /disabled=\{revokingClient !== null\}/);
    assert.match(ui, /onFinish: \(\) => setRevokingClient\(null\)/);
});

void test('clipboard failures have visible feedback', () => {
    assert.match(
        ui,
        /await navigator\.clipboard\.writeText\(service\.endpoint\)/,
    );
    assert.match(ui, /Copy unavailable/);
    assert.match(ui, /role="status"/);
});

void test('many OAuth grants have compact, searchable cards and unique client clues', () => {
    assert.match(ui, /visibleClients\.map\(\(client\)/);
    assert.match(ui, /matchingClients\.slice\(0, 5\)/);
    assert.match(ui, /client\.client_id\.slice\(-10\)/);
    assert.match(ui, /Search client name or scope/);
});

void test('offline recovery stays inside the KMJ-hosted device dashboard', () => {
    assert.match(recovery, /\/install-codebridge-windows\.cmd/);
    assert.match(recovery, /deviceId === 'kmj-homeoffice-desktop-5fvjmet'/);
    assert.match(recovery, /pendingProjects\.length === 0/);
    assert.match(recovery, /\/codebridge\/pair/);
    assert.match(recovery, /Reconnect Calibration Pro/);
    assert.match(deviceCenter, /deviceRecoveryAction\(device\.platform, \{/);
    assert.match(deviceCenter, /href=\{recovery\.href\}/);
    assert.match(deviceCenter, /\{recovery\.label\}/);
    assert.match(
        deviceCenter,
        /Registration ·\{' '\}\s*\{device\.id\.slice\(-8\)\}/,
    );
    assert.match(deviceCenter, /Registration\s+alone is not an/);
    assert.match(deviceCenter, /Live connection has not been verified/);
    assert.doesNotMatch(deviceCenter, /github\.com\/kmjtechno\/kmj-codebridge/);
    assert.doesNotMatch(
        ui,
        /raw\.githubusercontent\.com\/kmjtechno\/kmj-codebridge/,
    );
});

const hub = readSourceText(
    'resources/js/components/codebridge/control-center-hub.tsx',
);
const recovery = readSourceText(
    'resources/js/components/codebridge/device-recovery.mjs',
);

void test('control center provides working sections and scoped device onboarding', () => {
    for (const [target, source] of [
        ['codebridge-overview', hub],
        ['codebridge-device-control', deviceCenter],
        ['codebridge-usage', hub],
        ['codebridge-plan-billing', hub],
        ['codebridge-clients', ui],
        ['codebridge-settings', hub],
    ]) {
        assert.match(source, new RegExp(target));
    }
    assert.match(ui, /<CodeBridgeControlCenterHub/);
    assert.match(ui, /id="codebridge-clients"/);
    assert.match(hub, /href="\/codebridge\/pair"/);
    assert.match(hub, /href="\/settings\/security"/);
    assert.match(hub, /href="\/purchase"/);
});

void test('usage billing and device state never invent measurements or connectivity', () => {
    assert.match(hub, /No authoritative metering feed connected/);
    assert.match(hub, /Registration does not establish live presence/);
    assert.match(hub, /Refresh grants, not live app sessions/);
    assert.match(hub, /Invoices and paid consumption must be obtained/);
    assert.match(hub, /codeBridgeDeviceQuotaDisplay/);
    assert.doesNotMatch(hub, /connection_status === 'online'/);
    assert.doesNotMatch(hub, /100%|unlimited calls|live sessions/);
});

const deviceQuota = readSourceText(
    'resources/js/components/codebridge/device-policy-display.ts',
);

void test('owner numeric sentinel never appears as a customer-facing hard limit', () => {
    assert.match(deviceQuota, /OWNER_POLICY_DEVICE_CEILING = 2147483647/);
    assert.match(deviceQuota, /plan === 'owner'/);
    assert.match(deviceQuota, /Owner-tier technical ceiling/);
    assert.match(deviceQuota, /not live or executable capacity/);
    assert.match(deviceCenter, /codeBridgeDeviceQuotaDisplay/);
    assert.match(deviceCenter, /plan: string \| null/);
    assert.match(ui, /plan=\{service\.plan\}/);
    assert.doesNotMatch(deviceQuota, /unlimited device capacity/i);
});

void test('control center uses accessible section switching instead of one long dashboard', () => {
    assert.match(hub, /aria-pressed=\{activeSection === id\}/);
    assert.match(hub, /onSectionChange\(id\)/);
    assert.match(hub, /\{children\}/);
    assert.match(ui, /activeSection=\{activeSection\}/);
    assert.match(ui, /onSectionChange=\{setActiveSection\}/);
    for (const section of ['overview', 'devices', 'setup', 'clients']) {
        assert.match(ui, new RegExp(`activeSection === '${section}'`));
    }
    for (const section of ['overview', 'usage', 'billing', 'settings']) {
        assert.match(
            hub,
            new RegExp(`hidden=\\{activeSection !== '${section}'\\}`),
        );
    }
    assert.doesNotMatch(hub, /href=\{href\}/);
});

void test('CodeBridge customer controls avoid sub-12px utility labels', () => {
    for (const source of [ui, deviceCenter, hub]) {
        assert.doesNotMatch(source, /text-\[(?:9|10|11)px\]/);
    }
});

void test('CodeBridge dashboard uses the existing official product icon', () => {
    assert.match(ui, /src="\/assets\/kmj-codebridge-icon\.png"/);
    assert.match(ui, /alt="Official KMJ CodeBridge icon"/);
    assert.ok(existsSync('public/assets/kmj-codebridge-icon.png'));
    assert.doesNotMatch(ui, /laravel\.(?:svg|png)|<Cable className="h-7 w-7"/i);
    assert.match(ui, /setActiveSection\('devices'\)/);
});

const ownerDeviceSummary = readSourceText(
    'resources/js/pages/operator-codebridge-owner.tsx',
);
const ownerModuleNavigation = readSourceText(
    'resources/js/components/operator-module-navigation.tsx',
);

void test('one CodeBridge dashboard with owner-only license settings', () => {
    assert.match(ownerDeviceSummary, /Read-only summary:/);
    assert.match(ownerDeviceSummary, /connection not verified/);
    assert.match(ownerDeviceSummary, /Owner license settings/);
    assert.doesNotMatch(ownerDeviceSummary, /<DeviceControlCenter\b/);
    assert.match(
        ownerDeviceSummary,
        /href="\/services\/kmj-codebridge#codebridge-device-control"/,
    );
    assert.match(
        ownerModuleNavigation,
        /href: '\/services\/kmj-codebridge#codebridge-device-control'/,
    );
    assert.doesNotMatch(
        ownerModuleNavigation,
        /href: '\/operator\/codebridge\/owner-plan'/,
    );
    assert.match(ui, /codeBridgeSectionFromHash\(window\.location\.hash\)/);
    assert.match(ui, /window\.addEventListener\('hashchange', apply\)/);
    assert.match(ui, /window\.removeEventListener\('hashchange', apply\)/);
    assert.match(ui, /scrollIntoView\(\{\s*block: 'start'\s*\}\)/);
});

void test('repeated hash links scroll within the same CodeBridge tab', () => {
    assert.match(
        ui,
        /setHashNavigationRevision\(\(revision\) => revision \+ 1\)/,
    );
    assert.match(ui, /\[activeSection, hashNavigationRevision\]/);
    assert.match(ui, /pendingAnchor\.current = null/);
    assert.match(ui, /scrollIntoView\(\{\s*block: 'start'\s*\}\)/);
});

void test('one-click device/project setup is scoped to an existing exact grant, never a pending request', () => {
    const linux = {
        id: 'kmj-elite-main-platform',
        platform: 'linux',
        projects: [{ id: 'kmj-main-platform', name: 'Main Platform' }],
        pending_projects: [
            {
                id: 'kmj-cloudos',
                name: 'CloudOS',
                status: 'pending_local_setup',
            },
        ],
        pairing_state: 'redeemed',
    };
    assert.equal(
        deviceProjectConnectPlan(linux, 'kmj-main-platform')?.href,
        '/install',
    );
    assert.equal(deviceProjectConnectPlan(linux, 'kmj-cloudos'), null);
    assert.equal(deviceProjectConnectPlan(linux, 'vioso-clone'), null);
    assert.equal(
        deviceProjectConnectPlan(
            { ...linux, id: '../unknown' },
            'kmj-main-platform',
        ),
        null,
    );
    assert.equal(deviceProjectConnectPlan(linux, '../external'), null);
    assert.equal(deviceProjectConnectPlan(null, 'kmj-main-platform'), null);
    assert.equal(
        deviceProjectConnectPlan(
            { ...linux, projects: [] },
            'kmj-main-platform',
        ),
        null,
    );
});

void test('one-click routing never sends normal Linux or project-specific Windows grants to Calibration installer', () => {
    const windows = {
        id: 'kmj-kmj-codebridge-desktop-5fvjmet',
        platform: 'win32',
        projects: [{ id: 'kmj-codebridge', name: 'CodeBridge' }],
        pairing_state: 'redeemed',
    };
    const plan = deviceProjectConnectPlan(windows, 'kmj-codebridge');
    assert.equal(plan?.href, '/codebridge/pair');
    assert.equal(plan?.download, undefined);
    assert.match(plan?.guidance ?? '', /project-specific|Calibration Pro/i);
    assert.equal(
        deviceProjectConnectPlan(
            { ...windows, platform: 'linux' },
            'kmj-codebridge',
        )?.href,
        '/install',
    );
    assert.equal(
        deviceProjectConnectPlan(
            { ...windows, platform: 'darwin' },
            'kmj-codebridge',
        )?.href,
        '/codebridge-connect.html',
    );
    const calibration = {
        id: 'kmj-homeoffice-desktop-5fvjmet',
        platform: 'win32',
        projects: [{ id: 'kmj-calibration-pro', name: 'Calibration Pro' }],
        pending_projects: [],
        pairing_state: 'redeemed',
    };
    assert.equal(
        deviceProjectConnectPlan(calibration, 'kmj-calibration-pro')?.href,
        '/install-codebridge-windows.cmd',
    );
    assert.equal(
        deviceProjectConnectPlan(
            { ...calibration, pending_projects: [{ id: 'other' }] },
            'kmj-calibration-pro',
        )?.href,
        '/codebridge/pair',
    );
});

void test('unredeemed approval prompts existing enrollment review and never claims online', () => {
    const plan = deviceProjectConnectPlan(
        {
            id: 'kmj-elite-main-platform',
            platform: 'linux',
            projects: [{ id: 'kmj-main-platform', name: 'Main Platform' }],
            pairing_state: 'approved_unredeemed',
        },
        'kmj-main-platform',
    );
    assert.equal(plan?.label, 'Review existing enrollment');
    assert.match(plan?.guidance ?? '', /existing private enrollment/);
    assert.match(plan?.proof ?? '', /No verified gateway heartbeat/);
    assert.match(deviceCenter, /id="codebridge-device-project-connect"/);
    assert.match(deviceCenter, /Select authorized CodeBridge device/);
    assert.match(deviceCenter, /Select authorized CodeBridge project/);
    assert.match(
        deviceCenter,
        /deviceProjectConnectPlan\(connectDevice, connectProject\.id\)/,
    );
    assert.match(deviceCenter, /pending project\s+requests cannot be used/i);
    // Source normalization flattens line breaks; avoid scanning unrelated UI.
    // A nearby online claim is forbidden, but distant copy is not a claim.
    const falseOnlineClaim = /\bconnectPlan\b[^;]{0,300}\bonline\b/i;
    assert.doesNotMatch(deviceCenter, falseOnlineClaim);
    assert.match("const connectPlan = 'online';", falseOnlineClaim);
});

void test('CodeBridge owner quick actions are grouped responsively without losing destinations', () => {
    assert.match(ui, /aria-label="CodeBridge quick actions"/);
    assert.match(ui, /aria-label="Workspaces and integrations"/);
    assert.match(ui, /sm:grid-cols-2/);
    assert.match(ui, /2xl:grid-cols-\[minmax\(0,1fr\)_minmax\(420px,680px\)\]/);
    assert.match(ui, /min-h-11/);
    for (const label of [
        'Connect Windows PC',
        'Manage devices',
        'AI Workspace',
        'AI Providers',
        'Open in VS Code / Copilot',
        'Set up ChatGPT Desktop',
        'Approve pairing',
    ]) {
        assert.ok(
            ui.includes(label),
            'Missing working CodeBridge action: ' + label,
        );
    }
    assert.match(ui, /href="\/services\/kmj-codebridge\/workspace"/);
    assert.match(ui, /href="\/services\/kmj-codebridge\/ai-providers"/);
    assert.match(ui, /href="\/codebridge\/pair"/);
    assert.match(ui, /href=\{vscodeInstallUrl\(service\.endpoint\)\}/);
    assert.match(ui, /download="KMJ-CodeBridge-Connect-Windows\.cmd"/);
    assert.match(ui, /onClick=\{\(\) => setActiveSection\('devices'\)\}/);
});
