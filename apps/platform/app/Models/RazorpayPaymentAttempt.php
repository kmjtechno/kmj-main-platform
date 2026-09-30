<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;

final class RazorpayPaymentAttempt extends Model
{
    use HasUuids;

    protected $table = 'razorpay_payment_attempts';

    protected $fillable = [
        'order_id',
        'organization_id',
        'product_id',
        'plan_id',
        'requester_user_id',
        'idempotency_key',
        'receipt',
        'provider_order_id',
        'provider_payment_id',
        'currency',
        'amount_minor',
        'status',
        'failure_code',
        'refunded_amount_minor',
        'captured_at',
        'refunded_at',
    ];

    protected function casts(): array
    {
        return [
            'requester_user_id' => 'integer',
            'amount_minor' => 'integer',
            'refunded_amount_minor' => 'integer',
            'captured_at' => 'immutable_datetime',
            'refunded_at' => 'immutable_datetime',
        ];
    }
}
