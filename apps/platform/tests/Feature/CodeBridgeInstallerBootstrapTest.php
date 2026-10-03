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
            "CODEBRIDGE_RELEASE_REF='60bf446c40ce43aecd970ab703c224888671596f'",
            $script,
        );
        self::assertStringContainsString(
            'https://raw.githubusercontent.com/kmjtechno/kmj-codebridge/60bf446c40ce43aecd970ab703c224888671596f/scripts/install-vps.sh',
            $script,
        );
        self::assertStringContainsString("curl -fsSL --proto '=https' --tlsv1.2", $script);
        self::assertStringContainsString('export CODEBRIDGE_REF="$CODEBRIDGE_RELEASE_REF"', $script);
        self::assertStringNotContainsString('CODEBRIDGE_AGENT_TOKEN=', $script);
        self::assertStringNotContainsString('Authorization: Bearer ', $script);
    }
}
