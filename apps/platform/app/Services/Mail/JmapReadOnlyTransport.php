<?php

declare(strict_types=1);

namespace App\Services\Mail;

use GuzzleHttp\ClientInterface;
use RuntimeException;
use Throwable;
use UnexpectedValueException;

/**
 * Internal transport only. The caller must obtain a user-scoped credential and
 * expected username from an independently authorized server-side mailbox grant.
 * Never pass a user-supplied endpoint, shared administrator token or browser token.
 */
final class JmapReadOnlyTransport
{
    private const SESSION = 'https://mail.kmjtechno.com/jmap/session';

    private const MAX_BYTES = 2097152;

    public function __construct(private readonly ClientInterface $http) {}

    /**
     * @return list<array{id: string, name: string, parentId: ?string, role: ?string, sortOrder: int, totalEmails: int, unreadEmails: int}>
     */
    public function mailboxes(string $expectedUsername, #[\SensitiveParameter] string $token): array
    {
        $session = $this->authenticatedSession($expectedUsername, $token);

        $contract = new JmapMailboxContract;
        $account = $contract->primaryMailAccount($session);
        $response = $this->request('POST', $account['apiUrl'], $token, $contract->mailboxGet($session));

        return (new JmapMailboxResponse)->parse($session, $response);
    }

    /**
     * @return array{ids: list<string>, position: int, total: int}
     */
    public function inboxPage(string $expectedUsername, #[\SensitiveParameter] string $token, int $position = 0): array
    {
        if ($position < 0 || $position > 40000) {
            throw new UnexpectedValueException('Invalid KMJ Inbox position.');
        }

        $session = $this->authenticatedSession($expectedUsername, $token);
        $contract = new JmapMailboxContract;
        $account = $contract->primaryMailAccount($session);
        $mailboxes = $this->request('POST', $account['apiUrl'], $token, $contract->mailboxGet($session));
        $query = new JmapInboxQuery;
        $response = $this->request('POST', $account['apiUrl'], $token, $query->request($session, $mailboxes, $position));

        return $query->parse($session, $response, $position);
    }

    /** @return array<string, mixed> */
    private function authenticatedSession(string $expectedUsername, #[\SensitiveParameter] string $token): array
    {
        if ($expectedUsername === '' || strlen($expectedUsername) > 320
            || preg_match('/[\x00-\x1F\x7F]/', $expectedUsername) === 1
            || preg_match('/\A[A-Za-z0-9._~+\/-]{1,4096}=*\z/D', $token) !== 1
            || strlen($token) > 4096) {
            throw new UnexpectedValueException('Invalid KMJ mailbox credential binding.');
        }

        $session = $this->request('GET', self::SESSION, $token);
        if (($session['username'] ?? null) !== $expectedUsername) {
            throw new UnexpectedValueException('KMJ mailbox identity mismatch.');
        }

        return $session;
    }

    /**
     * @param  array<string, mixed>|null  $payload
     * @return array<string, mixed>
     */
    private function request(string $method, string $url, #[\SensitiveParameter] string $token, ?array $payload = null): array
    {
        try {
            $options = [
                'headers' => ['Authorization' => 'Bearer '.$token, 'Accept' => 'application/json'],
                'allow_redirects' => false,
                'http_errors' => false,
                'verify' => true,
                'stream' => true,
                'connect_timeout' => 5,
                'timeout' => 15,
                'read_timeout' => 5,
                'decode_content' => false,
            ];
            if ($payload !== null) {
                $options['json'] = $payload;
            }

            $response = $this->http->request($method, $url, $options);
            $body = $response->getBody();

            try {
                $contentType = strtolower(trim(explode(';', $response->getHeaderLine('Content-Type'), 2)[0]));
                if ($response->getStatusCode() !== 200 || $contentType !== 'application/json'
                    || ($body->getSize() !== null && $body->getSize() > self::MAX_BYTES)) {
                    throw new RuntimeException('Invalid KMJ mail HTTP response.');
                }

                $raw = '';
                $deadline = hrtime(true) + 15_000_000_000;
                while (! $body->eof()) {
                    $chunk = $body->read(min(8192, self::MAX_BYTES + 1 - strlen($raw)));
                    if ($chunk === '' || hrtime(true) > $deadline) {
                        throw new RuntimeException('Incomplete KMJ mail response.');
                    }
                    $raw .= $chunk;
                    if (strlen($raw) > self::MAX_BYTES) {
                        throw new RuntimeException('KMJ mail response exceeded limit.');
                    }
                }

                $decoded = json_decode($raw, true, 32, JSON_THROW_ON_ERROR);
                if (! is_array($decoded) || array_is_list($decoded)) {
                    throw new RuntimeException('Invalid KMJ mail response document.');
                }

                /** @var array<string, mixed> $decoded */
                return $decoded;
            } finally {
                $body->close();
            }
        } catch (Throwable) {
            // No provider response, request, token, URL query or underlying exception.
            throw new RuntimeException('KMJ mail transport unavailable.');
        }
    }
}
