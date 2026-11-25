<?php

declare(strict_types=1);

namespace Tests\Unit;

use App\Services\Mail\JmapReadOnlyTransport;
use GuzzleHttp\Client;
use GuzzleHttp\Handler\MockHandler;
use GuzzleHttp\HandlerStack;
use GuzzleHttp\Middleware;
use GuzzleHttp\Psr7\Response;
use PHPUnit\Framework\TestCase;
use RuntimeException;
use UnexpectedValueException;

final class JmapReadOnlyTransportTest extends TestCase
{
    public function test_requests_only_pinned_endpoints_with_redirects_disabled(): void
    {
        $history = [];
        $stack = HandlerStack::create(new MockHandler([
            $this->session(),
            new Response(200, ['Content-Type' => 'application/json'], '{"methodResponses":[["Mailbox/get",{"accountId":"a1","state":"s1","list":[],"notFound":[]},"mailboxes"]]}'),
        ]));
        $stack->push(Middleware::history($history));
        $transport = new JmapReadOnlyTransport(new Client(['handler' => $stack]));

        self::assertSame([], $transport->mailboxes('owner@example.test', 'test-token'));
        self::assertCount(2, $history);
        self::assertSame('https://mail.kmjtechno.com/jmap/session', (string) $history[0]['request']->getUri());
        self::assertSame('https://mail.kmjtechno.com/jmap/', (string) $history[1]['request']->getUri());
        self::assertSame('Bearer test-token', $history[1]['request']->getHeaderLine('Authorization'));
        self::assertFalse($history[0]['options']['allow_redirects']);
        self::assertTrue($history[0]['options']['verify']);
    }

    public function test_redirect_is_rejected_without_following_it(): void
    {
        $stack = HandlerStack::create(new MockHandler([
            new Response(307, ['Location' => 'https://example.invalid/']),
        ]));
        $transport = new JmapReadOnlyTransport(new Client(['handler' => $stack]));

        $this->expectException(RuntimeException::class);
        $this->expectExceptionMessage('KMJ mail transport unavailable.');
        $transport->mailboxes('owner@example.test', 'test-token');
    }

    public function test_wrong_authenticated_identity_is_rejected(): void
    {
        $stack = HandlerStack::create(new MockHandler([$this->session()]));
        $transport = new JmapReadOnlyTransport(new Client(['handler' => $stack]));

        $this->expectException(UnexpectedValueException::class);
        $this->expectExceptionMessage('KMJ mailbox identity mismatch.');
        $transport->mailboxes('other@example.test', 'test-token');
    }

    public function test_oversized_response_is_rejected(): void
    {
        $stack = HandlerStack::create(new MockHandler([
            new Response(200, ['Content-Type' => 'application/json'], str_repeat('x', 2097153)),
        ]));
        $transport = new JmapReadOnlyTransport(new Client(['handler' => $stack]));

        $this->expectException(RuntimeException::class);
        $transport->mailboxes('owner@example.test', 'test-token');
    }

    private function session(): Response
    {
        $mail = 'urn:ietf:params:jmap:mail';

        return new Response(200, ['Content-Type' => 'application/json'], json_encode([
            'username' => 'owner@example.test',
            'apiUrl' => 'https://mail.kmjtechno.com/jmap/',
            'capabilities' => ['urn:ietf:params:jmap:core' => new \stdClass, $mail => new \stdClass],
            'primaryAccounts' => [$mail => 'a1'],
            'accounts' => ['a1' => ['isPersonal' => true, 'accountCapabilities' => [$mail => new \stdClass]]],
        ], JSON_THROW_ON_ERROR));
    }
}
