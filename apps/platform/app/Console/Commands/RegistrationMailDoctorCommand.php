<?php

namespace App\Console\Commands;

use App\Services\Mail\RegistrationMailReadiness;
use Illuminate\Console\Command;

final class RegistrationMailDoctorCommand extends Command
{
    protected $signature = 'kmj:mail:doctor {--json}';

    protected $description = 'Read-only mail transport check for account verification (never prints credentials or tokens)';

    public function handle(RegistrationMailReadiness $readiness): int
    {
        $transport = (string) config('mail.default', '');
        $mailers = config('mail.mailers.'.$transport, []);
        $type = is_array($mailers) ? (string) ($mailers['transport'] ?? '') : '';
        // Loopback SMTP readiness can change between probes. Resolve once
        // so JSON state, explanation and exit code agree.
        $canAttemptDelivery = $readiness->canAttemptDelivery();

        $state = [
            'environment' => app()->environment(),
            'transport' => $type,
            'adapter' => $transport === 'kmj_brevo' ? 'temporary_brevo_free_smtps' : $transport,
            'can_attempt_external_delivery' => $canAttemptDelivery,
            'live_delivery_proven' => false,
            'diagnostic' => $canAttemptDelivery
                ? 'Mailer appears configured; verify provider acceptance, SPF/DKIM/DMARC and an actual recipient inbox.'
                : 'Verification mail is not externally deliverable with the active configuration. Configure authenticated SMTP or a supported transactional provider.',
        ];

        if ((bool) $this->option('json')) {
            $this->line((string) json_encode($state, JSON_UNESCAPED_SLASHES));
        } else {
            $this->components->info('KMJ registration email delivery readiness — no secrets');
            $this->table(['Check', 'Result'], [
                ['Environment', $state['environment']],
                ['Mailer type', $state['transport'] !== '' ? $state['transport'] : 'missing'],
                ['Active adapter', $state['adapter']],
                ['Can attempt external delivery', $state['can_attempt_external_delivery'] ? 'YES (not confirmed delivered)' : 'NO'],
                ['Recipient delivery verified', 'NO (requires real delivery test)'],
            ]);
            if (! $state['can_attempt_external_delivery']) {
                $this->components->error($state['diagnostic']);
            } else {
                $this->components->warn($state['diagnostic']);
            }
        }

        return $state['can_attempt_external_delivery'] ? self::SUCCESS : self::FAILURE;
    }
}
