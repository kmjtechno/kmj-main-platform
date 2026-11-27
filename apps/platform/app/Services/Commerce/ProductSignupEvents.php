<?php

declare(strict_types=1);

namespace App\Services\Commerce;

use App\Models\User;
use Illuminate\Auth\Events\Login;
use Illuminate\Auth\Events\Verified;
use Illuminate\Support\Facades\Event;
use Illuminate\Support\Facades\Log;
use Throwable;

/**
 * Connects "I signed up for this product" to sign-in and email verification,
 * for both password and Google accounts. A failure never blocks either.
 */
final class ProductSignupEvents
{
    public const SESSION_KEY = 'kmj_signup_product';

    public static function register(): void
    {
        Event::listen(Login::class, static function (Login $event): void {
            self::safely(static function () use ($event): void {
                if (! $event->user instanceof User) {
                    return;
                }

                $signups = app(ProductSignups::class);
                $slug = request()->hasSession()
                    ? request()->session()->pull(self::SESSION_KEY)
                    : null;

                if (is_string($slug)) {
                    $signups->record($event->user, $slug);
                } else {
                    $signups->fulfil($event->user);
                }
            });
        });

        Event::listen(Verified::class, static function (Verified $event): void {
            self::safely(static function () use ($event): void {
                if ($event->user instanceof User) {
                    app(ProductSignups::class)->fulfil($event->user);
                }
            });
        });
    }

    private static function safely(callable $work): void
    {
        try {
            $work();
        } catch (Throwable $exception) {
            // No message or personal data in logs.
            Log::warning('kmj_product_signup_failed', ['category' => $exception::class]);
        }
    }
}
