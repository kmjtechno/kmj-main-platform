<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Services\Licensing\OmniDesk\OmniDeskAutomaticTrialExpiry;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Schema;

final class ExpireOmniDeskTrials extends Command
{
    protected $signature = 'licensing:expire-omnidesk-trials {--limit=50}';

    protected $description = 'Audit and expire due first-party OmniDesk trials and corresponding entitlements';

    public function handle(OmniDeskAutomaticTrialExpiry $expiry): int
    {
        if (config('omnidesk-licensing.auto_expire_trials', false) !== true) {
            $this->line('OMNIDESK_TRIAL_EXPIRY=DISABLED_NO_MUTATION');

            return self::SUCCESS;
        }

        $limit = filter_var(
            $this->option('limit'),
            FILTER_VALIDATE_INT,
            ['options' => ['min_range' => 1, 'max_range' => 100]],
        );
        if ($limit === false) {
            $this->error('OMNIDESK_TRIAL_EXPIRY=INVALID_LIMIT');

            return self::INVALID;
        }

        foreach (['kslp_licenses', 'kslp_license_events', 'entitlements',
            'entitlement_policies', 'entitlement_ledger', 'products'] as $table) {
            if (! Schema::hasTable($table)) {
                $this->warn('OMNIDESK_TRIAL_EXPIRY=SCHEMA_NOT_READY_NO_MUTATION');

                return self::SUCCESS;
            }
        }

        $result = $expiry->expireDue($limit);
        $this->line(sprintf(
            'OMNIDESK_TRIAL_EXPIRY=COMPLETE expired=%d blocked=%d skipped=%d',
            $result['expired'],
            $result['blocked'],
            $result['skipped'],
        ));
        $this->line('PAYMENTS_CHANGED=NO PAID_LICENSES_CHANGED=NO SIGNER_CALLED=NO');

        // The ledger stays authoritative; a mismatch requires human review,
        // not forced data repair that might affect another customer's rights.
        return $result['blocked'] > 0 ? self::FAILURE : self::SUCCESS;
    }
}
