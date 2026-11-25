<?php

namespace Tests\Feature\Mail;

use App\Events\DomainOutboxPublished;
use App\Models\DomainOutboxMessage;
use App\Models\User;
use App\Notifications\BrandedCustomerNotification;
use App\Services\Events\LaravelEventOutboxPublisher;
use App\Services\Events\OutboxDispatcher;
use App\Services\Mail\BrandedCustomerMail;
use Illuminate\Auth\Events\Verified;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Event;
use Illuminate\Support\Facades\Notification;
use InvalidArgumentException;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Commerce\Services\CommercialOrderService;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class BrandedTransactionalSuiteTest extends TestCase
{
    use RefreshDatabase;

    /** @return array<string, array<string, mixed>> */
    private function fixtures(): array
    {
        $order = ['order' => 'order-test-2026-11', 'product' => 'KMJ CloudOS'];

        return [
            'welcome' => [],
            'order_received' => [...$order, 'state' => 'requested'],
            'order_confirmed' => [...$order, 'state' => 'confirmed'],
            'payment_receipt' => [
                ...$order, 'state' => 'confirmed', 'amount_minor' => 129900,
                'currency' => 'INR', 'reference' => 'provider-confirmation-test',
            ],
            'payment_failed' => [...$order, 'state' => 'failed'],
            'order_cancelled' => [...$order, 'state' => 'cancelled'],
            'license_issued' => [
                'state' => 'active', 'product' => 'KMJ OmniDesk', 'license_reference' => 'example-license-ref',
            ],
            'renewal_confirmed' => [
                'state' => 'renewed', 'product' => 'KMJ CloudOS', 'renewal_date' => '2027-11-22',
            ],
            'security_alert' => [],
            'support_update' => ['case' => 'CASE-100', 'status' => 'In progress'],
        ];
    }

    public function test_all_ten_email_variants_render_branded_responsive_html_and_plain_text(): void
    {
        foreach ($this->fixtures() as $kind => $context) {
            $message = BrandedCustomerMail::compose($kind, 'Asha', $context);
            self::assertSame([
                'html' => 'emails.kmj-transactional',
                'text' => 'emails.kmj-transactional-text',
            ], $message->view, $kind);
            self::assertNotEmpty($message->subject);

            $html = view('emails.kmj-transactional', $message->viewData)->render();
            $text = view('emails.kmj-transactional-text', $message->viewData)->render();

            self::assertStringContainsString('https://kmjtechno.com/assets/brand/mail/signature-red/header.jpg', $html, $kind);
            self::assertStringContainsString('https://kmjtechno.com/assets/brand/mail/signature-red/footer.jpg', $html, $kind);
            self::assertStringContainsString('INNOVATE | BUILD | SCALE', $html, $kind);
            self::assertStringContainsString('INNOVATE | BUILD | SCALE', $text, $kind);
            self::assertStringContainsString('Asha', $html, $kind);
            self::assertStringContainsString('Asha', $text, $kind);
            self::assertStringContainsString('viewport', $html, $kind);
            self::assertStringNotContainsString('<script', $html, $kind);
            self::assertStringNotContainsString('Unsubscribe', $html, $kind);
            self::assertStringContainsString('info@kmjtechno.com', $text, $kind);
        }
    }

    public function test_untrusted_content_is_escaped_and_links_are_first_party_only(): void
    {
        $data = [
            'state' => 'requested',
            'order' => '<script>alert("order")</script>',
            'product' => '<img src=x onerror=alert(1)>',
            'actionUrl' => 'https://attacker.example/token',
        ];

        $message = BrandedCustomerMail::compose('order_received', '<b>Customer</b>', $data);
        $html = view('emails.kmj-transactional', $message->viewData)->render();

        self::assertStringNotContainsString('<script>', $html);
        self::assertStringContainsString('&lt;script&gt;', $html);
        self::assertStringNotContainsString('<img src=x onerror', $html);
        self::assertStringContainsString('&lt;img src=x', $html);
        self::assertStringNotContainsString('attacker.example', $html);
        self::assertStringContainsString('/dashboard', $html);
    }

    public function test_cannot_claim_confirmed_payment_without_authoritative_state_and_amount(): void
    {
        foreach ([
            ['state' => 'requested', 'order' => 'a', 'product' => 'b', 'amount_minor' => 100, 'currency' => 'INR', 'reference' => 'c'],
            ['state' => 'confirmed', 'order' => 'a', 'product' => 'b', 'amount_minor' => 0, 'currency' => 'INR', 'reference' => 'c'],
            ['state' => 'confirmed', 'order' => 'a', 'product' => 'b', 'amount_minor' => 100, 'currency' => 'rupees', 'reference' => 'c'],
        ] as $bad) {
            try {
                BrandedCustomerMail::compose('payment_receipt', 'Asha', $bad);
                self::fail('Expected fail-closed payment receipt validation.');
            } catch (InvalidArgumentException) {
                self::assertTrue(true);
            }
        }
    }

    public function test_disabled_delivery_never_sends_welcome_or_order_notifications(): void
    {
        Notification::fake();
        config()->set('services.kmj_transactional_mail.enabled', false);
        $user = User::factory()->create();

        Event::dispatch(new Verified($user));
        Event::dispatch(new DomainOutboxPublished(new DomainOutboxMessage([
            'event_type' => 'commerce.order.requested',
            'aggregate_type' => 'commercial_order',
            'aggregate_id' => 'absent',
        ])));

        Notification::assertNothingSent();
    }

    public function test_verified_user_receives_welcome_when_owner_flag_and_real_mailer_config_enabled(): void
    {
        $this->enableTestDelivery();
        Notification::fake();
        $user = User::factory()->create();

        Event::dispatch(new Verified($user));

        Notification::assertSentTo(
            $user,
            BrandedCustomerNotification::class,
            fn (BrandedCustomerNotification $notice): bool => $notice->kind === 'welcome',
        );
    }

    public function test_committed_order_outbox_publishes_one_status_notice_and_replay_sends_nothing(): void
    {
        $this->enableTestDelivery();
        Notification::fake();
        $user = User::factory()->create();
        $organization = app(OrganizationCreator::class)->create('Mail QA Organization', $user->id);
        $product = Product::query()->create([
            'slug' => 'mail-test-product',
            'name' => 'KMJ Mail Test Product',
            'status' => 'preview',
        ]);
        $order = app(CommercialOrderService::class)->request(
            $organization->getKey(), $product->getKey(), $user->id, 'order-mail-once-test',
        );
        $message = DomainOutboxMessage::query()
            ->where('event_type', 'commerce.order.requested')
            ->where('aggregate_id', (string) $order->getKey())
            ->firstOrFail();

        $dispatcher = app(OutboxDispatcher::class);
        $publisher = app(LaravelEventOutboxPublisher::class);

        self::assertTrue($dispatcher->publishOne((string) $message->getKey(), $publisher));
        self::assertFalse($dispatcher->publishOne((string) $message->getKey(), $publisher));

        Notification::assertSentTo(
            $user,
            BrandedCustomerNotification::class,
            fn (BrandedCustomerNotification $notice): bool => $notice->kind === 'order_received'
                && $notice->context['order'] === (string) $order->getKey()
                && $notice->context['state'] === 'requested',
        );
        self::assertSame(1, $message->fresh()->attempts);
    }

    private function enableTestDelivery(): void
    {
        // Notification::fake prevents a real send. Config is test-only.
        config()->set('services.kmj_transactional_mail.enabled', true);
        config()->set('services.kmj_transactional_mail.send_payment_receipts', false);
        config()->set('services.kmj_transactional_mail.not_before', now()->subDay()->utc()->format('Y-m-d\\TH:i:s\\Z'));
        config()->set('mail.default', 'sendmail');
        config()->set('mail.from.address', 'info@kmjtechno.com');
    }
}
