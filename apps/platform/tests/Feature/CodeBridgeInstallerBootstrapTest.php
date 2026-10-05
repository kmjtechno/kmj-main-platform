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
        self::assertStringContainsString(
            'winget install --id OpenJS.NodeJS.LTS',
            $script,
        );
        self::assertStringContainsString('Refresh-ProcessPath', $script);
        self::assertStringNotContain
    public function test_chatgpt_desktop_launcher_is_pinned_verified_and_credential_free(): void
    {
        $response = $this->get('/install-chatgpt-desktop.cmd')
            ->assertOk()
            ->assertHeader('Content-Type', 'application/octet-stream')
            ->assertHeader(
                'Content-Disposition',
                'attachment; filename="KMJ-CodeBridge-ChatGPT-Desktop.cmd"',
            )
            ->assertHeader('X-Content-Type-Options', 'nosniff');

        $script = $response->getContent();
        self::assertIsString($script);
        self::assertStringStartsWith('@echo off', $script);
        self::assertStringContainsString(
            'KMJ_SETUP_REF=9b27cfa3fb38c7cb08e1fda0da8cec384e625b06',
            $script,
        );
        self::assertStringContainsString(
            'KMJ_SETUP_SHA256=ab82687d5ec6463925f415ae62bbdf0527073dac414de0ba0ad29c921c9a4bca',
            $script,
        );
        self::assertStringContainsString(
            'raw.githubusercontent.com/kmjtechno/kmj-codebridge/%KMJ_SETUP_REF%/scripts/install-chatgpt-desktop.ps1',
            $script,
        );
        self::assertStringContainsString('Get-FileHash -Algorithm SHA256', $script);
        self::assertStringContainsString('ExecutionPolicy Bypass', $script);
        self::assertStringNotContainsString('Authorization: Bearer ', $script);
        self::assertStringNotContainsString('client_secret', $script);
        self::assertStringNotContainsString('CODEBRIDGE_AGENT_TOKEN=', $script);
    }
sString('Authorization: Bearer ', $script);
        self::assertStringNotContainsString('client_secret', $script);
        self::assertStringNotContainsString('CODEBRIDGE_AGENT_TOKEN=', $script);
    }
}
