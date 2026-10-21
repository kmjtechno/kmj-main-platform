<?php

namespace App\Services\Mail;

use Illuminate\Auth\Notifications\ResetPassword;
use Illuminate\Auth\Notifications\VerifyEmail;
use Illuminate\Notifications\Messages\MailMessage;

/**
 * Use the existing signed Laravel verification and reset routes.
 * Presentation is branded, but account security semantics are unchanged.
 */
final class BrandedAuthNotifications
{
    public static function register(): void
    {
        VerifyEmail::toMailUsing(static function ($notifiable, string $url): MailMessage {
            $minutes = (int) config('auth.verification.expire', 60);

            return self::message(
                subject: 'Verify your email address | KMJ TECHNO',
                preheader: 'Securely verify your KMJ TECHNO account email address.',
                eyebrow: 'ACCOUNT SECURITY',
                heading: 'Verify your email address',
                intro: 'Welcome to KMJ TECHNO. Verify your email address to finish securing your account.',
                actionText: 'Verify email address',
                actionUrl: $url,
                expiryText: "For your security, this verification link expires in {$minutes} minutes.",
            );
        });

        ResetPassword::toMailUsing(static function ($notifiable, string $token): MailMessage {
            $url = route('password.reset', [
                'token' => $token,
                'email' => $notifiable->getEmailForPasswordReset(),
            ]);
            $minutes = (int) config('auth.passwords.'.config('auth.defaults.passwords').'.expire', 60);

            return self::message(
                subject: 'Reset your password | KMJ TECHNO',
                preheader: 'Use the secure password reset link for your KMJ TECHNO account.',
                eyebrow: 'SECURE ACCOUNT RECOVERY',
                heading: 'Reset your password',
                intro: 'We received a request to reset your KMJ TECHNO account password. Use the secure link below to continue.',
                actionText: 'Reset my password',
                actionUrl: $url,
                expiryText: "For your security, this password reset link expires in {$minutes} minutes.",
            );
        });
    }

    private static function message(
        string $subject,
        string $preheader,
        string $eyebrow,
        string $heading,
        string $intro,
        string $actionText,
        string $actionUrl,
        string $expiryText,
    ): MailMessage {
        return (new MailMessage)
            ->subject($subject)
            ->view([
                'html' => 'emails.kmj-auth-transactional',
                'text' => 'emails.kmj-auth-transactional-text',
            ], [
                'subject' => $subject,
                'preheader' => $preheader,
                'eyebrow' => $eyebrow,
                'heading' => $heading,
                'intro' => $intro,
                'actionText' => $actionText,
                'actionUrl' => $actionUrl,
                'expiryText' => $expiryText,
            ]);
    }
}
