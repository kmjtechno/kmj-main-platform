<?php

namespace App\Services\Mail;

use Illuminate\Support\Facades\Config;

/**
 * Safely report whether mail is configured for an external delivery attempt.
 *
 * This is a configuration check, not proof of SMTP acceptance or inbox delivery.
 * Never expose credentials, recipient addresses, reset tokens or signed links.
 */
final class RegistrationMailReadiness
{
    public function canAttemptDelivery(): bool
    {
        $mailer = trim((string) Config::get('mail.default', ''));

        if ($mailer === '') {
            return false;
        }

        $from = (string) Config::get('mail.from.address', '');

        if (filter_var($from, FILTER_VALIDATE_EMAIL) === false
            || strtolower($from) === 'hello@example.com') {
            return false;
        }

        return $this->canAttemptWithMailer($mailer, []);
    }

    /**
     * @param  array<string, true>  $seen
     */
    private function canAttemptWithMailer(string $name, array $seen): bool
    {
        if (isset($seen[$name])) {
            return false;
        }

        $seen[$name] = true;
        $mailer = Config::get("mail.mailers.{$name}");

        if (! is_array($mailer)) {
            return false;
        }

        $transport = $mailer['transport'] ?? null;

        if (! is_string($transport)) {
            return false;
        }

        if (in_array($transport, ['log', 'array'], true)) {
            return false;
        }

        if (in_array($transport, ['failover', 'roundrobin'], true)) {
            $children = $mailer['mailers'] ?? null;

            // A logging/array fallback could mark a send successful while
            // delivering nothing. Do not present such a chain as ready.
            if (! is_array($children) || $children === []) {
                return false;
            }

            foreach ($children as $child) {
                if (! is_string($child) || ! $this->canAttemptWithMailer($child, $seen)) {
                    return false;
                }
            }

            return true;
        }

        if ($transport === 'smtp') {
            // Credential-based free relay is opt-in, unlike a bare remote
            // SMTP hostname. This prevents a nonexistent SMTP key or a
            // non-verified sender domain from unblocking registration.
            if (($mailer['kmj_requires_credentials'] ?? false) === true) {
                if (($mailer['kmj_activation_confirmed'] ?? false) !== true) {
                    return false;
                }

                $username = $mailer['username'] ?? null;
                $password = $mailer['password'] ?? null;

                if (! is_string($username) || filter_var($username, FILTER_VALIDATE_EMAIL) === false
                    || ! is_string($password) || strlen($password) < 15) {
                    return false;
                }

                $requiredDomain = strtolower(trim((string) ($mailer['kmj_required_sender_domain'] ?? '')));

                $sender = strtolower(trim((string) Config::get('mail.from.address', '')));

                if ($requiredDomain === '' || ! str_ends_with($sender, '@'.$requiredDomain)) {
                    return false;
                }

                // Port 465 with implicit TLS prevents downgrade to cleartext
                // credentials. An alternative TLS policy requires review.
                if (($mailer['scheme'] ?? null) !== 'smtps' || (int) ($mailer['port'] ?? 0) !== 465) {
                    return false;
                }
            }

            $host = trim((string) ($mailer['host'] ?? ''));

            if ($host === '') {
                return false;
            }

            // Casting malformed ports such as "587junk" to 587 could falsely
            // enable registration even though the transport cannot connect.
            $port = filter_var($mailer['port'] ?? null, FILTER_VALIDATE_INT);

            if ($port === false || $port < 1 || $port > 65535) {
                return false;
            }

            $normalizedHost = strtolower($host);
            if (in_array($normalizedHost, ['0.0.0.0', '::', '[::]'], true)) {
                return false; // Wildcard bind addresses are not SMTP peers.
            }

            // Every supported loopback spelling must confirm a listener;
            // otherwise IPv6 localhost is incorrectly treated as remote SMTP.
            // Do not probe arbitrary remote hosts in this readiness check.
            $isIpv6Loopback = in_array($normalizedHost, ['::1', '[::1]'], true);
            $isIpv4Loopback = in_array($normalizedHost, ['127.0.0.1', 'localhost'], true);

            if ($isIpv4Loopback || $isIpv6Loopback) {
                if ($port === 2525) {
                    return false; // Laravel's example/development default.
                }

                $errorCode = 0;
                $errorMessage = '';
                $target = $isIpv6Loopback ? '[::1]' : '127.0.0.1';
                $connection = @stream_socket_client(
                    sprintf('tcp://%s:%d', $target, $port),
                    $errorCode,
                    $errorMessage,
                    0.2,
                    STREAM_CLIENT_CONNECT,
                );

                if ($connection === false) {
                    return false;
                }

                fclose($connection);
            }

            return true;
        }

        // Built-in remote provider transports can attempt external delivery,
        // but their authentication and provider acceptance are NOT verified.
        return in_array($transport, ['ses', 'ses-v2', 'postmark', 'resend', 'mailgun', 'sendmail'], true);
    }
}
