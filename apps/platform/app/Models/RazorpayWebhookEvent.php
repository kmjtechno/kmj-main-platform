<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

final class RazorpayWebhookEvent extends Model
{
    protected $table = 'razorpay_webhook_events';

    protected $primaryKey = 'event_id';

    public $incrementing = false;

    protected $keyType = 'string';

    protected $fillable = [
        'event_id',
        'event_type',
        'payload_sha256',
        'payment_attempt_id',
        'processed_at',
    ];

    protected function casts(): array
    {
        return ['processed_at' => 'immutable_datetime'];
    }
}
