<?php

declare(strict_types=1);

namespace Tests\Unit;

use App\Services\Mail\JmapMailboxContract;
use PHPUnit\Framework\TestCase;
use UnexpectedValueException;

final class JmapMailboxContractTest extends TestCase
{
    private const MAIL = 'urn:ietf:params:jmap:mail';

    public function test_read_only_request_is_bound_to_primary_personal_account(): void
    {
        $contract = new JmapMailboxContract;
        $session = $this->session();

        self::assertSame([
            'apiUrl' => 'https://mail.kmjtechno.com/jmap/',
            'accountId' => 'a1',
        ], $contract->primaryMailAccount($session));

        $request = $contract->mailboxGet($session);
        self::assertSame('Mailbox/get', $request['methodCalls'][0][0]);
        self::assertSame('a1', $request['methodCalls'][0][1]['accountId']);
        self::assertNull($request['methodCalls'][0][1]['ids']);
    }

    public function test_untrusted_endpoint_is_rejected(): void
    {
        $contract = new JmapMailboxContract;
        foreach ([
            'http://mail.kmjtechno.com/jmap',
            'https://mail.kmjtechno.com.evil.invalid/jmap',
            'https://mail.kmjtechno.com@evil.invalid/jmap',
            'https://mail.kmjtechno.com/jmap?redirect=evil',
            'https://mail.kmjtechno.com:8443/jmap',
        ] as $url) {
            $session = $this->session();
            $session['apiUrl'] = $url;
            try {
                $contract->mailboxGet($session);
                self::fail('Untrusted API URL accepted.');
            } catch (UnexpectedValueException) {
                self::assertTrue(true);
            }
        }
    }

    public function test_shared_or_missing_primary_account_is_rejected(): void
    {
        $contract = new JmapMailboxContract;
        $session = $this->session();
        $session['primaryAccounts'][self::MAIL] = 'shared';
        $this->expectException(UnexpectedValueException::class);
        $contract->mailboxGet($session);
    }

    public function test_mail_capability_is_required(): void
    {
        $contract = new JmapMailboxContract;
        $session = $this->session();
        unset($session['capabilities'][self::MAIL]);
        $this->expectException(UnexpectedValueException::class);
        $contract->mailboxGet($session);
    }

    /** @return array<string, mixed> */
    private function session(): array
    {
        return [
            'apiUrl' => 'https://mail.kmjtechno.com/jmap/',
            'capabilities' => ['urn:ietf:params:jmap:core' => [], self::MAIL => []],
            'primaryAccounts' => [self::MAIL => 'a1'],
            'accounts' => [
                'a1' => ['isPersonal' => true, 'accountCapabilities' => [self::MAIL => []]],
                'shared' => ['isPersonal' => false, 'accountCapabilities' => [self::MAIL => []]],
            ],
        ];
    }
}
