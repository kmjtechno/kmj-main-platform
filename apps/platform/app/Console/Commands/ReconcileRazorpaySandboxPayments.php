<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Services\Payments\OwnerPaymentGatewaySettings;
use App\Services\Payments\RazorpayWebhookReconciler;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Schema;
use InvalidArgumentException;

/**
 * Automatic server-side SANDBOX reconciliation. This is the receipt→confirmed
 * commercial-order stage only, NOT a license/entitlement/payment issuer.
 * Live payment processing requires an independently approved adapter.
 */
final class ReconcileRazorpaySandboxPayments extends Command
{
    protected $signature = 'payments:reconcile-razorpay-sandbox {--limit=25}';

    protected $description = 'Reconcile pending signed Razorpay sandbox webhooks against provider-captured payments';

    public function handle(
        RazorpayWebhookReconciler $reconciler,
        OwnerPaymentGatewaySettings $settings,
    ): int {
        // Never turn a stored test key into an implied live charging grant.
        if (! app()->environment(['local', 'testing', 'staging'])) {
            $this->components->warn('RECONCILIATION=SKIPPED_PRODUCTION_REVIEW_REQUIRED');

            return self::SUCCESS;
        }

        $limit = filter_var(
            $this->option('limit'),
            FILTER_VALIDATE_INT,
            ['options' => ['min_range' => 1, 'max_range' => 100]],
        );
        if ($limit === false) {
            $this->components->error('RECONCILIATION=INVALID_LIMIT');

            return self::INVALID;
        }

        if (! Schema::hasTable('payment_webhook_events')
            || ! Schema::hasTable('commerce_provider_orders')
            || ! Schema::hasTable('commerce_orders')) {
            $this->components->warn('RECONCILIATION=SKIPPED_SCHEMA_NOT_READY');

            return self::SUCCESS;
        }

        // Having an encrypted owner vault credential does not prove merchant
        // approval. Strict sandbox key validation happens inside this call.
        try {
            $settings->sandboxCredentials('razorpay');
        } catch (InvalidArgumentException) {
            $this->components->warn('RECONCILIATION=SKIPPED_SANDBOX_CREDENTIALS_ABSENT');

            return self::SUCCESS;
        }

        $result = $reconciler->reconcilePending($limit);
        $this->line(sprintf(
            'RECONCILIATION=SANDBOX_ONLY_CONFIRMED_ORDERS reconciled=%d unmatched=%d rejected=%d retry_later=%d',
            $result['reconciled'],
            $result['unmatched'],
            $result['rejected'],
            $result['retry_later'],
        ));
        $this->line('ENTITLEMENT_ISSUED=NO LICENSE_ISSUED=NO PAYMENT_CHARGED=NO');

        return self::SUCCESS;
    }
}
