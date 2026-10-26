<?php

namespace Tests\Feature;

use Tests\TestCase;

final class CodeBridgeInstallerBootstrapTest extends TestCase
{
    public function test_public_installer_bootstrap_is_pinned_and_credential_free(): void
    {
        $response = $this->get('/install')
            ->assertOk()
            ->assertHeader('Content-Type', 'text/x-shellscript; charset=UTF-8')
            ->assertHeader('X-Content-Type-Options', 'nosniff');

        $script = $response->getContent();
        self::assertIsString($script);
        self::assertStringStartsWith("#!/usr/bin/env bash\n", $script);
        self::assertStringContainsString(
            "CODEBRIDGE_RELEASE_REF='ff8a64273ce46e6ddcae1c62e054917be8572b4e'",
            $script,
        );
        self::assertStringContainsString(
            'https://raw.githubusercontent.com/kmjtechno/kmj-codebridge/ff8a64273ce46e6ddcae1c62e054917be8572b4e/scripts/install-vps.sh',
            $script,
        );
        self::assertStringContainsString("curl -fsSL --proto '=https' --tlsv1.2", $script);
        self::assertStringContainsString('export CODEBRIDGE_REF="$CODEBRIDGE_RELEASE_REF"', $script);
        self::assertStringNotContainsString('CODEBRIDGE_AGENT_TOKEN=', $script);
        self::assertStringNotContainsString('Authorization: Bearer ', $script);
    }

    public function test_windows_device_installer_is_first_party_pinned_and_checksum_verified(): void
    {
        $scriptResponse = $this->get('/install-codebridge-windows.ps1')
            ->assertOk()
            ->assertHeader('Content-Type', 'text/plain; charset=UTF-8')
            ->assertHeader('X-Content-Type-Options', 'nosniff');
        $script = $scriptResponse->getContent();
        self::assertIsString($script);
        self::assertStringContainsString(
            '$pin = \'9c35bdbe999f702a6c19fde22c7baeefa3c8894f\'',
            $script,
        );
        self::assertStringContainsString('git clone', $script);
        self::assertStringContainsString('checkout --detach $pin', $script);
        self::assertStringContainsString('npm ci --omit=dev --ignore-scripts', $script);
        self::assertStringContainsString('ONE-CLICK-ANY-DEVICE.ps1', $script);
        // P520 reconnect must not ask the owner to choose a second device ID.
        self::assertStringContainsString('DESKTOP-5FVJMET', $script);
        self::assertStringContainsString('ONE-CLICK-AGENT-AUTOCONNECT.ps1', $script);
        self::assertStringContainsString('& $connector -Device HomeOffice', $script);
        self::assertStringContainsString('KMJ_DEVICE_SCOPE=P520_HOME_OFFICE_CALIBRATION_PRO', $script);
        self::assertStringContainsString('KMJ-CaliPro\\toolchains', $script);
        self::assertStringContainsString('KMJ_NODE24=EXISTING_VERIFIED', $script);
        self::assertStringContainsString('KMJ_GLOBAL_PATH_CHANGED=NO', $script);
        self::assertStringNotContainsString('Set-ExecutionPolicy', $script);
        self::assertStringNotContainsString('git reset', $script);
        self::assertStringNotContainsString('git clean', $script);
        self::assertStringContainsString('KMJ_RUNTIME_UNTRUSTED_OR_MODIFIED', $script);
        self::assertStringContainsString('ACCOUNT_READY=CHECK_AUTHENTICATED_GATEWAY_STATUS', $script);
        self::assertStringNotContainsString('CODEBRIDGE_AGENT_TOKEN=', $script);
        self::assertStringNotContainsString('Authorization: Bearer', $script);

        $download = $this->get('/install-codebridge-windows.cmd')
            ->assertOk()
            ->assertHeader('Content-Type', 'application/octet-stream')
            ->assertHeader('X-Content-Type-Options', 'nosniff')
            ->assertHeader('Cache-Control', 'no-store, private')
            ->assertHeader(
                'Content-Disposition',
                'attachment; filename="KMJ-CodeBridge-Connect-Windows.cmd"',
            );
        $launcher = $download->getContent();
        self::assertIsString($launcher);
        self::assertStringStartsWith("@echo off\n", str_replace("\r\n", "\n", $launcher));
        self::assertStringContainsString('https://kmjtechno.com/install-codebridge-windows.ps1', $launcher);
        self::assertStringContainsString(strtoupper(hash('sha256', $script)), $launcher);
        self::assertStringContainsString('Get-FileHash -LiteralPath $p -Algorithm SHA256', $launcher);
        self::assertStringNotContainsString('%%EXPECTED_SHA256%%', $launcher);
        self::assertStringNotContainsString('ExecutionPolicy Bypass', $launcher);
        self::assertStringNotContainsString('Authorization: Bearer', $launcher);
    }

    public function test_chatgpt_desktop_setup_uses_public_marketplace_without_credentials(): void
    {
        $response = $this->get('/install-chatgpt-desktop.ps1')
            ->assertOk()
            ->assertHeader('Content-Type', 'text/plain; charset=UTF-8')
            ->assertHeader(
                'Content-Disposition',
                'attachment; filename="KMJ-CodeBridge-ChatGPT-Desktop.ps1"',
            )
            ->assertHeader('X-Content-Type-Options', 'nosniff');

        $script = $response->getContent();
        self::assertIsString($script);
        self::assertStringContainsString(
            'codex plugin marketplace add $repo --ref main',
            $script,
        );
        self::assertStringContainsString(
            '$repo = \'kmjtechno/kmj-codebridge\'',
            $script,
        );
        self::assertStringContainsString(
            'codex plugin marketplace upgrade $marketplace',
            $script,
        );
        self::assertStringContainsString(
            'Codex CLI was not found; using the ChatGPT Desktop personal-marketplace fallback.',
            $script,
        );
        self::assertStringContainsString(
            '.codex\\plugins\\kmj-codebridge',
            $script,
        );
        self::assertStringContainsString(
            '.agents\\plugins\\marketplace.json',
            $script,
        );
        self::assertStringContainsString(
            './../../.codex/plugins/kmj-codebridge',
            $script,
        );
        self::assertStringContainsString(
            'INSTALLED_BY_DEFAULT',
            $script,
        );
        self::assertStringContainsString(
            'https://github.com/kmjtechno/kmj-codebridge/archive/refs/heads/main.zip',
            $script,
        );
        self::assertStringNotContainsString('Authorization: Bearer ', $script);
        self::assertStringNotContainsString('client_secret', $script);
        self::assertStringNotContainsString('CODEBRIDGE_AGENT_TOKEN=', $script);
    }
}
