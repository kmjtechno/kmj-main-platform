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

    public function test_inbox_transport_derives_folder_and_reads_only_validated_page(): void
    {
        $history = [];
        $stack = HandlerStack::create(new MockHandler([
            $this->session(),
            new Response(200, ['Content-Type' => 'application/json'], '{"methodResponses":[["Mailbox/get",{"accountId":"a1","state":"s1","list":[{"id":"inbox1","name":"Inbox","parentId":null,"role":"inbox","sortOrder":0,"totalEmails":1,"unreadEmails":1}],"notFound":[]},"mailboxes"]]}'),
            new Response(200, ['Content-Type' => 'application/json'], '{"methodResponses":[["Email/query",{"accountId":"a1","queryState":"q1","position":0,"ids":["e1"],"total":1},"inbox-query"]]}'),
        ]));
        $stack->push(Middleware::history($history));
        $transport = new JmapReadOnlyTransport(new Client(['handler' => $stack]));

        self::assertSame(['ids' => ['e1'], 'position' => 0, 'total' => 1], $transport->inboxPage('owner@example.test', 'test-token'));
        self::assertCount(3, $history);
        self::assertSame('https://mail.kmjtechno.com/jmap/', (string) $history[2]['request']->getUri());
        $request = json_decode((string) $history[2]['request']->getBody(), true, 32, JSON_THROW_ON_ERROR);
        self::assertSame('Email/query', $request['methodCalls'][0][0]);
        self::assertSame(['inMailbox' => 'inbox1'], $request['methodCalls'][0][1]['filter']);
        self::assertSame('a1', $request['methodCalls'][0][1]['accountId']);
    }

    public function test_inbox_invalid_position_never_makes_request(): void
    {
        $history = [];
        $stack = HandlerStack::create(new MockHandler([]));
        $stack->push(Middleware::history($history));
        $transport = new JmapReadOnlyTransport(new Client(['handler' => $stack]));

        try {
            $transport->inboxPage('owner@example.test', 'test-token', -1);
            self::fail('Invalid Inbox position accepted.');
        } catch (UnexpectedValueException) {
            self::assertSame([], $history);
        }
    }

    public function test_inbox_summary_reads_metadata_from_validated_query_in_same_session(): void
    {
        $history = [];
        $stack = HandlerStack::create(new MockHandler([
            $this->session(),
            new Response(200, ['Content-Type' => 'application/json'], '{"methodResponses":[["Mailbox/get",{"accountId":"a1","state":"s1","list":[{"id":"inbox1","name":"Inbox","parentId":null,"role":"inbox","sortOrder":0,"totalEmails":1,"unreadEmails":1}],"notFound":[]},"mailboxes"]]}'),
            new Response(200, ['Content-Type' => 'application/json'], '{"methodResponses":[["Email/query",{"accountId":"a1","queryState":"q1","position":0,"ids":["e1"],"total":1},"inbox-query"]]}'),
            new Response(200, ['Content-Type' => 'application/json'], '{"methodResponses":[["Email/get",{"accountId":"a1","state":"s1","list":[{"id":"e1","threadId":"t1","receivedAt":"2026-11-25T12:00:00Z","subject":"Test","from":[{"name":"Sender","email":"sender@example.test"}],"keywords":{"$seen":true},"hasAttachment":false}],"notFound":[]},"inbox-metadata"]]}'),
        ]));
        $stack->push(Middleware::history($history));
        $transport = new JmapReadOnlyTransport(new Client(['handler' => $stack]));
        $result = $transport->inboxSummary('owner@example.test', 'test-token');
        self::assertSame('e1', $result['messages'][0]['id']);
        self::assertSame(1, $result['total']);
        self::assertSame([], $result['missing']);
        self::assertCount(4, $history);
        $request = json_decode((string) $history[3]['request']->getBody(), true, 32, JSON_THROW_ON_ERROR);
        self::assertSame('Email/get', $request['methodCalls'][0][0]);
        self::assertSame(['e1'], $request['methodCalls'][0][1]['ids']);
        self::assertSame('a1', $request['methodCalls'][0][1]['accountId']);
    }

    public function test_empty_inbox_summary_does_not_request_metadata(): void
    {
        $history = [];
        $stack = HandlerStack::create(new MockHandler([
            $this->session(),
            new Response(200, ['Content-Type' => 'application/json'], '{"methodResponses":[["Mailbox/get",{"accountId":"a1","state":"s1","list":[{"id":"inbox1","name":"Inbox","parentId":null,"role":"inbox","sortOrder":0,"totalEmails":0,"unreadEmails":0}],"notFound":[]},"mailboxes"]]}'),
            new Response(200, ['Content-Type' => 'application/json'], '{"methodResponses":[["Email/query",{"accountId":"a1","queryState":"q1","position":0,"ids":[],"total":0},"inbox-query"]]}'),
        ]));
        $stack->push(Middleware::history($history));
        $transport = new JmapReadOnlyTransport(new Client(['handler' => $stack]));
        self::assertSame(['messages' => [], 'missing' => [], 'position' => 0, 'total' => 0], $transport->inboxSummary('owner@example.test', 'test-token'));
        self::assertCount(3, $history);
    }

    public function test_non_json_content_type_is_rejected(): void
    {
        $stack = HandlerStack::create(new MockHandler([
            new Response(200, ['Content-Type' => 'text/html'], '{"username":"owner@example.test"}'),
        ]));
        $transport = new JmapReadOnlyTransport(new Client(['handler' => $stack]));

        $this->expectException(RuntimeException::class);
        $this->expectExceptionMessage('KMJ mail transport unavailable.');
        $transport->mailboxes('owner@example.test', 'test-token');
    }

    public function test_unauthorized_status_is_rejected(): void
    {
        $stack = HandlerStack::create(new MockHandler([
            new Response(401, ['Content-Type' => 'application/json'], '{"username":"owner@example.test"}'),
        ]));
        $transport = new JmapReadOnlyTransport(new Client(['handler' => $stack]));

        $this->expectException(RuntimeException::class);
        $this->expectExceptionMessage('KMJ mail transport unavailable.');
        $transport->mailboxes('owner@example.test', 'test-token');
    }

    public function test_malformed_token_never_makes_a_request(): void
    {
        $history = [];
        $stack = HandlerStack::create(new MockHandler([]));
        $stack->push(Middleware::history($history));
        $transport = new JmapReadOnlyTransport(new Client(['handler' => $stack]));

        foreach (['bad token', "bad\ntoken", ''] as $token) {
            try {
                $transport->mailboxes('owner@example.test', $token);
                self::fail('Malformed token must be rejected.');
            } catch (UnexpectedValueException $e) {
                self::assertSame('Invalid KMJ mailbox credential binding.', $e->getMessage());
            }
        }
        self::assertCount(0, $history);
    }

    public function test_foreign_api_url_in_session_is_never_requested(): void
    {
        $mail = 'urn:ietf:params:jmap:mail';
        $history = [];
        $stack = HandlerStack::create(new MockHandler([
            new Response(200, ['Content-Type' => 'application/json'], json_encode([
                'username' => 'owner@example.test',
                'apiUrl' => 'https://evil.example.invalid/jmap/',
                'capabilities' => ['urn:ietf:params:jmap:core' => new \stdClass, $mail => new \stdClass],
                'primaryAccounts' => [$mail => 'a1'],
                'accounts' => ['a1' => ['isPersonal' => true, 'accountCapabilities' => [$mail => new \stdClass]]],
            ], JSON_THROW_ON_ERROR)),
        ]));
        $stack->push(Middleware::history($history));
        $transport = new JmapReadOnlyTransport(new Client(['handler' => $stack]));

        try {
            $transport->mailboxes('owner@example.test', 'test-token');
            self::fail('A foreign apiUrl must be rejected.');
        } catch (\Throwable) {
            // Expected: the contract rejects the session.
        }
        self::assertCount(1, $history);
        self::assertSame('mail.kmjtechno.com', $history[0]['request']->getUri()->getHost());
    }

    public function test_failure_message_never_contains_the_token(): void
    {
        $stack = HandlerStack::create(new MockHandler([
            new Response(500, ['Content-Type' => 'application/json'], '{}'),
        ]));
        $transport = new JmapReadOnlyTransport(new Client(['handler' => $stack]));

        try {
            $transport->mailboxes('owner@example.test', 'secret-token-value');
            self::fail('Expected failure.');
        } catch (RuntimeException $e) {
            self::assertStringNotContainsString('secret-token-value', $e->getMessage());
            self::assertStringNotContainsString('secret-token-value', (string) $e->getPrevious()?->getMessage());
        }
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
