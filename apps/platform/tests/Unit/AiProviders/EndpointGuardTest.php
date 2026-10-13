<?php

declare(strict_types=1);

namespace Tests\Unit\AiProviders;

use App\Services\AiProviders\EndpointGuard;
use App\Services\AiProviders\FreePolicy;
use InvalidArgumentException;
use PHPUnit\Framework\TestCase;
use RuntimeException;

final class EndpointGuardTest extends TestCase
{
    private const APPROVED = ['api.groq.com'];

    public function test_a_public_https_endpoint_is_accepted_and_pinned(): void
    {
        $guard = new EndpointGuard(fn (): array => ['93.184.216.34']);

        $this->assertSame(
            ['host' => 'api.groq.com', 'ip' => '93.184.216.34', 'base' => 'https://api.groq.com/openai/v1'],
            $guard->validate('https://api.groq.com/openai/v1/', self::APPROVED),
        );
    }

    /** @return array<string, array{string, string}> */
    public static function rejectedUrls(): array
    {
        return [
            'plain http' => ['http://api.groq.com/v1', 'endpoint_scheme'],
            'credentials in url' => ['https://user:pw@api.groq.com/v1', 'endpoint_userinfo'],
            'odd port' => ['https://api.groq.com:8443/v1', 'endpoint_port'],
            'ip literal' => ['https://93.184.216.34/v1', 'endpoint_host'],
            'loopback literal' => ['https://127.0.0.1/v1', 'endpoint_host'],
            'ipv6 literal' => ['https://[::1]/v1', 'endpoint_host'],
            'single label host' => ['https://localhost/v1', 'endpoint_host'],
            'query string' => ['https://api.groq.com/v1?x=1', 'endpoint_path'],
            'traversal' => ['https://api.groq.com/v1/../admin', 'endpoint_path'],
            'not approved' => ['https://evil.example.com/v1', 'endpoint_not_approved'],
        ];
    }

    /** @dataProvider rejectedUrls */
    public function test_unsafe_endpoints_are_rejected(string $url, string $code): void
    {
        $guard = new EndpointGuard(fn (): array => ['93.184.216.34']);

        $this->expectException(InvalidArgumentException::class);
        $this->expectExceptionMessage($code);
        $guard->validate($url, self::APPROVED);
    }

    /** @return array<string, array{list<string>}> */
    public static function privateAnswers(): array
    {
        return [
            'rfc1918' => [['10.0.0.5']],
            'loopback' => [['127.0.0.1']],
            'link local metadata' => [['169.254.169.254']],
            'carrier grade nat' => [['100.64.1.1']],
            'ipv6 loopback' => [['::1']],
            'ipv6 unique local' => [['fd00::1']],
            'ipv4 mapped loopback' => [['::ffff:127.0.0.1']],
            'public mixed with private' => [['93.184.216.34', '10.0.0.5']],
            'unresolvable' => [[]],
        ];
    }

    /** @dataProvider privateAnswers
     * @param  list<string>  $answers
     */
    public function test_dns_answers_that_are_not_all_public_are_rejected(array $answers): void
    {
        $guard = new EndpointGuard(fn (): array => $answers);

        $this->expectException(InvalidArgumentException::class);
        $guard->validate('https://api.groq.com/v1', self::APPROVED);
    }

    public function test_zero_spend_policy(): void
    {
        $this->assertTrue(FreePolicy::inferenceAllowed('plan', true, 'any'));
        $this->assertTrue(FreePolicy::inferenceAllowed('model-suffix', true, 'meta/llama:free'));
        $this->assertFalse(FreePolicy::inferenceAllowed('model-suffix', true, 'meta/llama'));
        $this->assertFalse(FreePolicy::inferenceAllowed('none', true, 'gpt'));
        $this->assertTrue(FreePolicy::inferenceAllowed('none', false, 'gpt'), 'explicit paid opt-in');

        $this->expectException(RuntimeException::class);
        FreePolicy::assertInferenceAllowed('none', true, 'gpt');
    }
}
