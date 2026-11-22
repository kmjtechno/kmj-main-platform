<?php

namespace App\Services\Mail;

use Illuminate\Notifications\Messages\MailMessage;
use InvalidArgumentException;

/**
 * Reviewable presentation catalog for *transactional* KMJ customer notices.
 *
 * Every action links to the first-party account. No caller-supplied URL or
 * HTML is accepted. These are templates, not evidence that an order settled,
 * a license was issued, or an email reached the recipient.
 */
final class BrandedCustomerMail
{
    /** @param array<string, mixed> $context */
    public static function compose(string $kind, string $recipientName, array $context = []): MailMessage
    {
        $greeting = 'Hello '.self::field(['name' => $recipientName], 'name', 100).',';

        $catalog = match ($kind) {
            'welcome' => [
                'subject' => 'Welcome to KMJ TECHNO',
                'category' => 'WELCOME',
                'eyebrow' => 'YOUR ACCOUNT IS READY',
                'heading' => 'Welcome to what comes next.',
                'preheader' => 'Your KMJ TECHNO email is verified. Explore your secure account.',
                'intro' => 'Your email address is verified. Your KMJ TECHNO account is ready to explore. Discover our products, manage your profile and follow your services from one place.',
                'notice' => 'A verified email does not automatically activate a product, subscription or license.',
                'action' => 'Go to my dashboard',
            ],
            'order_received' => [
                'subject' => 'We received your order request | KMJ TECHNO',
                'category' => 'ORDERS',
                'eyebrow' => 'ORDER REQUEST RECEIVED',
                'heading' => 'Your request is with us.',
                'preheader' => 'Your KMJ TECHNO order request has been recorded.',
                'intro' => 'We have received your order request. We will share an update after the order has been reviewed or payment confirmed. No payment or license activation is implied by this notice.',
                'notice' => 'Order status: Requested. Keep this email for your records.',
                'action' => 'View my account',
            ],
            'order_confirmed' => [
                'subject' => 'Your order is confirmed | KMJ TECHNO',
                'category' => 'ORDERS',
                'eyebrow' => 'ORDER CONFIRMED',
                'heading' => 'Confirmed. Thank you.',
                'preheader' => 'Your KMJ TECHNO order confirmation details are ready.',
                'intro' => 'Your order has been confirmed against recorded commercial evidence. You can follow the next steps in your account.',
                'notice' => 'Order confirmation and payment records are separate from product access or license activation.',
                'action' => 'View my account',
            ],
            'payment_receipt' => [
                'subject' => 'Payment confirmation | KMJ TECHNO',
                'category' => 'PAYMENTS',
                'eyebrow' => 'PAYMENT RECORDED',
                'heading' => 'Payment confirmed.',
                'preheader' => 'Your verified KMJ TECHNO payment has been recorded.',
                'intro' => 'We have recorded the confirmed payment shown below. This is a transaction acknowledgement, not a tax invoice or evidence that a license is active.',
                'notice' => 'Keep your payment reference. For a formal invoice, use the invoice supplied by the authorized billing workflow.',
                'action' => 'View my account',
            ],
            'payment_failed' => [
                'subject' => 'Payment update | KMJ TECHNO',
                'category' => 'PAYMENTS',
                'eyebrow' => 'PAYMENT NOT CONFIRMED',
                'heading' => 'Your payment needs attention.',
                'preheader' => 'A KMJ TECHNO payment attempt could not be confirmed.',
                'intro' => 'We could not confirm this payment attempt. Please review your payment status before trying again. If your bank shows a debit, contact support with your order reference.',
                'notice' => 'Do not retry a payment until you have checked the current status. We will never ask for your card PIN or OTP.',
                'action' => 'Review my account',
            ],
            'order_cancelled' => [
                'subject' => 'Order cancellation confirmed | KMJ TECHNO',
                'category' => 'ORDERS',
                'eyebrow' => 'ORDER CANCELLED',
                'heading' => 'Your order was cancelled.',
                'preheader' => 'Your KMJ TECHNO order cancellation has been recorded.',
                'intro' => 'The order identified below has been cancelled. If money was debited, refund handling is separate and follows the applicable payment process.',
                'notice' => 'This notice is not a refund confirmation.',
                'action' => 'View my account',
            ],
            'license_issued' => [
                'subject' => 'Your license is ready | KMJ TECHNO',
                'category' => 'LICENSING',
                'eyebrow' => 'LICENSE ACTIVATED',
                'heading' => 'Your license is ready.',
                'preheader' => 'Your KMJ TECHNO license activation is recorded.',
                'intro' => 'Your license has been activated through the authorized licensing workflow. Sign in to review its product access and terms.',
                'notice' => 'Never share license keys, private activation tokens or account recovery credentials by email.',
                'action' => 'Open my dashboard',
            ],
            'renewal_confirmed' => [
                'subject' => 'Subscription renewed | KMJ TECHNO',
                'category' => 'SUBSCRIPTIONS',
                'eyebrow' => 'RENEWAL CONFIRMED',
                'heading' => 'Your service continues.',
                'preheader' => 'Your KMJ TECHNO subscription renewal has been confirmed.',
                'intro' => 'Your subscription renewal has been recorded. Your account displays the current service and its applicable renewal details.',
                'notice' => 'Billing, service access and entitlement states are governed separately by the platform.',
                'action' => 'Review subscription',
            ],
            'security_alert' => [
                'subject' => 'Important account security update | KMJ TECHNO',
                'category' => 'ACCOUNT SECURITY',
                'eyebrow' => 'SECURITY NOTIFICATION',
                'heading' => 'Account activity notice.',
                'preheader' => 'An account security change was recorded for KMJ TECHNO.',
                'intro' => 'A security-related action was recorded for your account. If this was not you, open KMJ TECHNO directly and contact our support team.',
                'notice' => 'We never ask for your password, OTP or recovery codes by email. For safety, open your browser and type kmjtechno.com yourself.',
                'action' => null,
            ],
            'support_update' => [
                'subject' => 'Support case update | KMJ TECHNO',
                'category' => 'SUPPORT',
                'eyebrow' => 'SUPPORT UPDATE',
                'heading' => 'An update on your request.',
                'preheader' => 'There is an update about your KMJ TECHNO support request.',
                'intro' => 'We have recorded an update on your support request. Review the reference below, and contact our team if you need additional assistance.',
                'notice' => 'Please do not reply with credentials or personal security codes.',
                'action' => 'Open my account',
            ],
            default => throw new InvalidArgumentException('Unsupported transactional notification kind.'),
        };

        // Fail closed if a caller attempts to imply a commercial fact that
        // has not been verified by its authoritative workflow.
        $requiredState = match ($kind) {
            'order_received' => 'requested',
            'order_confirmed', 'payment_receipt' => 'confirmed',
            'order_cancelled' => 'cancelled',
            'payment_failed' => 'failed',
            'license_issued' => 'active',
            'renewal_confirmed' => 'renewed',
            default => null,
        };
        if ($requiredState !== null && ($context['state'] ?? null) !== $requiredState) {
            throw new InvalidArgumentException('Transactional notice requires the authoritative state.');
        }

        $fields = match ($kind) {
            'welcome', 'security_alert' => [],
            'support_update' => ['case' => 'Case reference', 'status' => 'Current status'],
            'license_issued' => ['product' => 'Product', 'license_reference' => 'License reference'],
            'renewal_confirmed' => ['product' => 'Subscription', 'renewal_date' => 'Renewal date'],
            default => ['order' => 'Order reference', 'product' => 'Product'],
        };

        $details = [];
        foreach ($fields as $key => $label) {
            $details[] = ['label' => $label, 'value' => self::field($context, $key, 180)];
        }

        if ($kind === 'payment_receipt') {
            $amountMinor = $context['amount_minor'] ?? null;
            $currency = $context['currency'] ?? null;
            if (! is_int($amountMinor) || $amountMinor <= 0 || ! is_string($currency)
                || preg_match('/\A[A-Z]{3}\z/D', $currency) !== 1) {
                throw new InvalidArgumentException('Payment confirmation requires positive amount and ISO currency.');
            }

            $details[] = ['label' => 'Amount', 'value' => $currency.' '.number_format($amountMinor / 100, 2, '.', ',')];
            $details[] = ['label' => 'Payment reference', 'value' => self::field($context, 'reference', 180)];
        }

        $actionUrl = $catalog['action'] !== null ? url('/dashboard') : null;

        return (new MailMessage)
            ->subject($catalog['subject'])
            ->view([
                'html' => 'emails.kmj-transactional',
                'text' => 'emails.kmj-transactional-text',
            ], [
                'subject' => $catalog['subject'],
                'preheader' => $catalog['preheader'],
                'eyebrow' => $catalog['eyebrow'],
                'category' => $catalog['category'],
                'heading' => $catalog['heading'],
                'greeting' => $greeting,
                'intro' => $catalog['intro'],
                'notice' => $catalog['notice'],
                'details' => $details,
                'actionUrl' => $actionUrl,
                'actionText' => $catalog['action'],
            ]);
    }

    /** @param array<string, mixed> $values */
    private static function field(array $values, string $key, int $maxLength): string
    {
        $value = $values[$key] ?? null;
        if (! is_string($value) || trim($value) === '' || mb_strlen($value) > $maxLength
            || str_contains($value, "\r") || str_contains($value, "\n")) {
            throw new InvalidArgumentException('A required notification detail is invalid.');
        }

        return trim($value);
    }
}
