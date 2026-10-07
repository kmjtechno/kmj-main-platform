<?php

declare(strict_types=1);

namespace Tests\Unit;

use App\Services\CodeBridge\OAuth\OAuthCore;
use DomainException;
use PHPUnit\Framework\TestCase;

final class CodeBridgeOAuthCoreTest extends TestCase
{
    public function test_pkce_accepts_only_matching_s256_verifier(): void
    {
        $verifier = str_repeat('a', 43).'-._~';
        $challenge = OAuthCore::base64Url(hash('sha256', $verifier, true));

        self::assertTrue(OAuthCore::verifyPkce($verifier, $challenge));
        self::assertFalse(OAuthCore::verifyPkce($verifier.'x', $challenge));
        self::assertFalse(OAuthCore::verifyPkce(str_repeat('a', 42), OAuthCore::base64Url(hash('sha256', str_repeat('a', 42), true))));
        self::assertFalse(OAuthCore::verifyPkce(str_repeat('a', 129), $challenge));
        self::assertFalse(OAuthCore::verifyPkce($verifier, $verifier));
        self::assertFalse(OAuthCore::isValidChallenge('plain-challenge'));
    }

    public function test_redirect_registration_allows_https_and_loopback_only(): void
    {
        foreach ([
            'https://claude.ai/api/mcp/auth_callback',
            'https://chatgpt.com/connector_platform_oauth_redirect',
            'http://localhost/callback',
            'http://127.0.0.1:3118/callback',
            'http://[::1]/callback',
        ] as $ok) {
            self::assertTrue(OAuthCore::isRegistrableRedirect($ok), $ok);
        }
        foreach ([
            '', 'http://evil.example/callback', 'https://a.example/cb#frag', 'https://user:pw@a.example/cb',
            'javascript:alert(1)', 'https://a.example/c b', "https://a.example/\n", 'custom-scheme://cb', '/relative',
            'https://a.example/'.str_repeat('x', 600),
        ] as $bad) {
            self::assertFalse(OAuthCore::isRegistrableRedirect($bad), $bad);
        }
    }

    public function test_redirect_matching_is_exact_except_loopback_port(): void
    {
        $registered = ['https://claude.ai/api/mcp/auth_callback', 'http://localhost/callback', 'http://127.0.0.1/callback'];

        self::assertTrue(OAuthCore::redirectMatches($registered, 'https://claude.ai/api/mcp/auth_callback'));
        self::assertTrue(OAuthCore::redirectMatches($registered, 'http://localhost:3118/callback'));
        self::assertTrue(OAuthCore::redirectMatches($registered, 'http://127.0.0.1:50000/callback'));
        self::assertFalse(OAuthCore::redirectMatches($registered, 'https://claude.ai/api/mcp/auth_callback/'));
        self::assertFalse(OAuthCore::redirectMatches($registered, 'https://claude.ai:444/api/mcp/auth_callback'));
        self::assertFalse(OAuthCore::redirectMatches($registered, 'http://localhost:3118/other'));
        self::assertFalse(OAuthCore::redirectMatches($registered, 'https://localhost/callback'));
        self::assertFalse(OAuthCore::redirectMatches($registered, 'http://evil.example/callback'));
    }

    public function test_scopes_are_restricted_to_codebridge_scopes(): void
    {
        self::assertSame(['codebridge:read'], OAuthCore::parseScopes(null));
        self::assertSame(['codebridge:read', 'codebridge:write'], OAuthCore::parseScopes('codebridge:read  codebridge:write codebridge:read'));
        self::assertSame(['openid', 'codebridge:read'], OAuthCore::parseScopes('openid codebridge:read'));
        $this->expectException(DomainException::class);
        OAuthCore::parseScopes('codebridge:read admin');
    }

    public function test_jwt_is_ed25519_signed_and_verifiable_with_published_jwk(): void
    {
        $seed = random_bytes(SODIUM_CRYPTO_SIGN_SEEDBYTES);
        $secret = OAuthCore::decodeSigningKey(base64_encode($seed));
        self::assertSame(SODIUM_CRYPTO_SIGN_SECRETKEYBYTES, strlen($secret));

        $jwt = OAuthCore::signJwt(['sub' => 'user:1', 'aud' => 'https://bridge.example/mcp'], $secret, 'k1');
        [$h, $p, $s] = explode('.', $jwt);
        $header = json_decode(base64_decode(strtr($h, '-_', '+/')), true);
        self::assertSame(['alg' => 'EdDSA', 'typ' => 'at+jwt', 'kid' => 'k1'], $header);

        $jwk = OAuthCore::publicJwk($secret, 'k1');
        self::assertSame('OKP', $jwk['kty']);
        self::assertArrayNotHasKey('d', $jwk);
        $public = base64_decode(strtr($jwk['x'], '-_', '+/').'=');
        $signature = base64_decode(strtr($s, '-_', '+/').str_repeat('=', (4 - strlen($s) % 4) % 4));
        self::assertTrue(sodium_crypto_sign_verify_detached($signature, $h.'.'.$p, $public));
        self::assertFalse(sodium_crypto_sign_verify_detached($signature, $h.'.'.$p.'x', $public));
    }

    public function test_invalid_signing_keys_are_rejected(): void
    {
        self::assertSame('', OAuthCore::decodeSigningKey(null));
        self::assertSame('', OAuthCore::decodeSigningKey('not base64!'));
        self::assertSame('', OAuthCore::decodeSigningKey(base64_encode('short')));
        $this->expectException(DomainException::class);
        OAuthCore::signJwt([], 'short', 'k1');
    }

    public function test_secrets_are_unique_and_hashed(): void
    {
        $a = OAuthCore::secret();
        self::assertMatchesRegularExpression('/\A[A-Za-z0-9_-]{43}\z/', $a);
        self::assertNotSame($a, OAuthCore::secret());
        self::assertSame(hash('sha256', $a), OAuthCore::hashSecret($a));
    }
}
