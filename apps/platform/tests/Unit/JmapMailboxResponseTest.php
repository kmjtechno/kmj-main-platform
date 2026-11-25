<?php

declare(strict_types=1);

namespace Tests\Unit;

use App\Services\Mail\JmapMailboxResponse;
use PHPUnit\Framework\TestCase;
use UnexpectedValueException;

final class JmapMailboxResponseTest extends TestCase
{
    public function test_valid_account_bound_mailbox_is_normalized(): void
    {
        $response = new JmapMailboxResponse;
        self::assertSame([$this->mailbox()], $response->parse($this->session(), $this->response()));
    }

    public function test_foreign_account_is_rejected(): void
    {
        $response = new JmapMailboxResponse;
        $this->expectException(UnexpectedValueException::class);
        $response->parse($this->session(), $this->response('other'));
    }

    public function test_wrong_method_call_id_is_rejected(): void
    {
        $response = new JmapMailboxResponse;
        $this->expectException(UnexpectedValueException::class);
        $response->parse($this->session(), $this->response(callId: 'other'));
    }

    public function test_invalid_counters_and_duplicate_records_are_rejected(): void
    {
        $response = new JmapMailboxResponse;
        $mailbox = $this->mailbox();
        foreach ([[$mailbox, $mailbox], [array_replace($mailbox, ['unreadEmails' => 3])]] as $list) {
            try {
                $response->parse($this->session(), $this->response(list: $list));
                self::fail('Invalid mailbox result was accepted.');
            } catch (UnexpectedValueException) {
                self::assertTrue(true);
            }
        }
    }

    public function test_empty_mailbox_list_is_valid(): void
    {
        self::assertSame([], (new JmapMailboxResponse)->parse($this->session(), $this->response(list: [])));
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

    /** @return array{id: string, name: string, parentId: null, role: string, sortOrder: int, totalEmails: int, unreadEmails: int} */
    private function mailbox(): array
    {
        return [
            'id' => 'm1',
            'name' => 'Inbox',
            'parentId' => null,
            'role' => 'inbox',
            'sortOrder' => 0,
            'totalEmails' => 2,
            'unreadEmails' => 1,
        ];
    }

    /**
     * @param  list<array<string, mixed>>|null  $list
     * @return array<string, mixed>
     */
    private function response(string $account = 'a1', string $callId = 'mailboxes', ?array $list = null): array
    {
        return [
            'methodResponses' => [
                ['Mailbox/get', [
                    'accountId' => $account,
                    'state' => 's1',
                    'list' => $list ?? [$this->mailbox()],
                    'notFound' => [],
                ], $callId],
            ],
        ];
    }
}
