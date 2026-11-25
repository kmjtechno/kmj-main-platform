<?php

declare(strict_types=1);

namespace Tests\Unit;

use App\Services\Mail\JmapInboxMetadata;
use PHPUnit\Framework\TestCase;
use UnexpectedValueException;

final class JmapInboxMetadataTest extends TestCase
{
    public function test_request_excludes_message_content_and_uses_bound_account(): void
    {
        $request = (new JmapInboxMetadata)->request($this->session(), ['e1', 'e2']);
        $call = $request['methodCalls'][0];
        self::assertSame('Email/get', $call[0]);
        self::assertSame('a1', $call[1]['accountId']);
        self::assertSame(['e1', 'e2'], $call[1]['ids']);
        self::assertSame(['id', 'threadId', 'receivedAt', 'subject', 'from', 'keywords', 'hasAttachment'], $call[1]['properties']);
    }

    public function test_response_preserves_query_order_and_explicit_missing(): void
    {
        $result = (new JmapInboxMetadata)->parse($this->session(), ['e1', 'e2', 'e3'], $this->response([$this->entry('e3'), $this->entry('e1')], ['e2']));
        self::assertSame(['e1', 'e3'], array_column($result['messages'], 'id'));
        self::assertSame(['e2'], $result['missing']);
        self::assertTrue($result['messages'][0]['isRead']);
        self::assertFalse($result['messages'][0]['isFlagged']);
        self::assertArrayNotHasKey('htmlBody', $result['messages'][0]);
    }

    public function test_empty_page_is_valid(): void
    {
        self::assertSame(['messages' => [], 'missing' => []], (new JmapInboxMetadata)->parse($this->session(), [], $this->response([])));
    }

    public function test_foreign_duplicate_and_unaccounted_messages_are_denied(): void
    {
        foreach ([
            $this->response([$this->entry('e1')], [], 'foreign'),
            $this->response([$this->entry('foreign')]),
            $this->response([$this->entry('e1')], ['e1']),
            $this->response([]),
            $this->response([$this->entry('e1', ['receivedAt' => '2026-02-30T12:00:00Z'])]),
            $this->response([$this->entry('e1', ['subject' => str_repeat('x', 4097)])]),
            $this->response([$this->entry('e1', ['keywords' => ['$seen' => false]])]),
            $this->response([$this->entry('e1', ['from' => [['email' => "abc\n@example.test"]]])]),
        ] as $response) {
            try {
                (new JmapInboxMetadata)->parse($this->session(), ['e1'], $response);
                self::fail('Invalid metadata was accepted.');
            } catch (UnexpectedValueException) {
                self::assertTrue(true);
            }
        }
    }

    public function test_duplicate_request_ids_are_denied(): void
    {
        $this->expectException(UnexpectedValueException::class);
        (new JmapInboxMetadata)->request($this->session(), ['e1', 'e1']);
    }

    private function session(): array
    {
        $mail = 'urn:ietf:params:jmap:mail';

        return [
            'apiUrl' => 'https://mail.kmjtechno.com/jmap/',
            'capabilities' => ['urn:ietf:params:jmap:core' => [], $mail => []],
            'primaryAccounts' => [$mail => 'a1'],
            'accounts' => ['a1' => ['isPersonal' => true, 'accountCapabilities' => [$mail => []]]],
        ];
    }

    private function entry(string $id, array $overrides = []): array
    {
        return array_replace([
            'id' => $id,
            'threadId' => 't1',
            'receivedAt' => '2026-11-25T12:00:00Z',
            'subject' => 'Test message',
            'from' => [['name' => 'Test sender', 'email' => 'sender@example.test']],
            'keywords' => ['$seen' => true],
            'hasAttachment' => false,
            'htmlBody' => ['unrequested'],
        ], $overrides);
    }

    private function response(array $messages, array $missing = [], string $account = 'a1'): array
    {
        return ['methodResponses' => [
            ['Email/get', [
                'accountId' => $account,
                'state' => 's1',
                'list' => $messages,
                'notFound' => $missing,
            ], 'inbox-metadata'],
        ]];
    }
}
