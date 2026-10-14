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
            $host = trim((string) ($mailer['host'] ?? ''));

            if ($host === '') {
                return false;
            }

            $port = (int) ($mailer['port'] ?? 0);

            if ($port < 1 || $port > 65535) {
                return false;
            }

            // A configured local relay is not usable if the loopback listener
            // is absent. Probe only localhost, never arbitrary remote hosts.
            // This remains an attempt-readiness check, NOT inbox delivery proof.
            if (in_array(strtolower($host), ['127.0.0.1', 'localhost'], true)) {
                if ($port === 2525) {
                    return false; // Laravel's example/development default.
                }

                $connection = @fsockopen('127.0.0.1', $port, $errorCode, $errorMessage, 0.2);

                if (! is_resource($connection)) {
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
