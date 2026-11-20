<?php

namespace App\Console\Commands;

use App\Services\Payments\RazorpayWebhookReconciler;
use Illuminate\Console\Command;

final class ReconcileRazorpayWebhooksCommand extends Command
{
    protected $signature = 'payments:reconcile-razorpay {--limit=50}';

    protected $description = 'Confirm commercial orders from verified Razorpay webhook events using provider evidence (sandbox; no entitlements)';

    public function handle(RazorpayWebhookReconciler $reconciler): int
    {
        $totals = $reconciler->reconcilePending((int) $this->option('limit'));
        $this->line((string) json_encode($totals, JSON_UNESCAPED_SLASHES));

        return self::SUCCESS;
    }
}
