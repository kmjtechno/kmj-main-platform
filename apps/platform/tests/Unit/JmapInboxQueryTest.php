<?php

declare(strict_types=1);

namespace Tests\Unit;

use App\Services\Mail\JmapInboxQuery;
use PHPUnit\Framework\TestCase;
use UnexpectedValueException;

final class JmapInboxQueryTest extends TestCase
{
    public function test_request_derives_inbox_from_authenticated_mailboxes(): void
    {
        $request = (new JmapInboxQuery)->request($this->session(), $this->mailboxes(), 40);
        self::assertSame('Email/query', $request['methodCalls'][0][0]);
        self::assertSame(['inMailbox' => 'inbox1'], $request['methodCalls'][0][1]['filter']);
        self::assertSame('a1', $request['methodCalls'][0][1]['accountId']);
        self::assertSame(40, $request['methodCalls'][0][1]['limit']);
        self::assertSame(40, $request['methodCalls'][0][1]['position']);
    }

    public function test_missing_inbox_is_denied(): void
    {
        $response = $this->mailboxes();
        $response['methodResponses'][0][1]['list'] = [];
        $this->expectException(UnexpectedValueException::class);
        (new JmapInboxQuery)->request($this->session(), $response);
    }

    public function test_query_response_is_bound_and_normalized(): void
    {
        self::assertSame(['ids' => ['e1'], 'position' => 0, 'total' => 1], (new JmapInboxQuery)->parse($this->session(), $this->response()));
    }

    public function test_foreign_account_and_duplicate_ids_are_rejected(): void
    {
        foreach ([
            ['accountId' => 'other'],
            ['ids' => ['e1', 'e1'], 'total' => 2],
            ['position' => 1],
            ['ids' => array_fill(0, 41, 'e1'), 'total' => 41],
        ] as $override) {
            $response = $this->response();
            $response['methodResponses'][0][1] = array_replace($response['methodResponses'][0][1], $override);
            try {
                (new JmapInboxQuery)->parse($this->session(), $response);
                self::fail('Invalid query result accepted.');
            } catch (UnexpectedValueException) {
                self::assertTrue(true);
            }
        }
    }

    /** @return array<string, mixed> */
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

    /** @return array<string, mixed> */
    private function mailboxes(): array
    {
        return ['methodResponses' => [
            ['Mailbox/get', ['accountId' => 'a1', 'state' => 's1', 'notFound' => [], 'list' => [
                ['id' => 'inbox1', 'name' => 'Inbox', 'parentId' => null, 'role' => 'inbox', 'sortOrder' => 0, 'totalEmails' => 1, 'unreadEmails' => 1],
                ['id' => 'sent1', 'name' => 'Sent', 'parentId' => null, 'role' => 'sent', 'sortOrder' => 1, 'totalEmails' => 2, 'unreadEmails' => 0],
            ]], 'mailboxes'],
        ]];
    }

    /** @return array<string, mixed> */
    private function response(): array
    {
        return ['methodResponses' => [
            ['Email/query', ['accountId' => 'a1', 'queryState' => 'q1', 'position' => 0, 'ids' => ['e1'], 'total' => 1], 'inbox-query'],
        ]];
    }
}
