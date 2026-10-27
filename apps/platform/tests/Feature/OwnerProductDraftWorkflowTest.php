<?php

namespace Tests\Feature;

use App\Models\User;
use App\Services\Seo\PublicInitialMetadata;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;
use Inertia\Testing\AssertableInertia as Assert;
use KMJ\MainPlatform\Catalog\Models\Product;
use Tests\TestCase;

final class OwnerProductDraftWorkflowTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
        Cache::forget('product-studio-cloud-cooldown');
    }

    public function test_draft_generation_requires_a_verified_passkey_owner_and_recent_confirmation(): void
    {
        Http::preventStrayRequests();
        $this->postJson('/operator/products/draft', ['name' => 'KMJ Test'])->assertUnauthorized();
        $this->actingAs(User::factory()->create(['email_verified_at' => now()]))
            ->withSession(['auth.password_confirmed_at' => time()])
            ->postJson('/operator/products/draft', ['name' => 'KMJ Test'])->assertForbidden();
        $this->actingAs($this->owner())->withSession(['auth.password_confirmed_at' => 0])
            ->postJson('/operator/products/draft', ['name' => 'KMJ Test'])->assertStatus(423);
        Http::assertNothingSent();
    }

    public function test_unconfigured_generation_never_returns_template_content_as_ai(): void
    {
        Http::preventStrayRequests();
        config(['product_studio.text.enabled' => false]);
        $this->actingAs($this->owner())->withSession(['auth.password_confirmed_at' => time()])
            ->postJson('/operator/products/draft', ['name' => 'KMJ Test', 'category' => 'developer'])
            ->assertStatus(503)->assertJsonPath('code', 'GENERATION_UNAVAILABLE');
        Http::assertNothingSent();
        self::assertSame(0, Product::query()->count());
    }

    public function test_verified_free_cloud_returns_reviewable_unsaved_content_without_commercial_fields(): void
    {
        config(['product_studio.text.enabled' => true, 'product_studio.text.api_key' => 'test-only-not-a-key', 'product_studio.text.model' => 'openrouter/free']);
        Http::fake(['openrouter.ai/api/v1/models' => Http::response(['data' => [['id' => 'openrouter/free', 'pricing' => ['prompt' => '0', 'completion' => '0']]]]), 'openrouter.ai/api/v1/chat/completions' => Http::response([
            'usage' => ['cost' => 0], 'choices' => [['finish_reason' => 'stop', 'message' => ['content' => json_encode([
                'summary' => 'A proposed engineering workspace.',
                'headline' => 'KMJ Draft Workspace',
                'description' => 'Draft product information to review.',
                'features' => ['Proposed project workspace'],
                'faqs' => [['question' => 'Is it released?', 'answer' => 'Release status must be verified.']],
                'photo_prompt' => 'Engineering workspace, no text.',
                'banner_prompt' => 'Wide engineering workspace, no text.',
                'purchase_enabled' => true,
            ], JSON_THROW_ON_ERROR)]]],
        ])]);
        $this->actingAs($this->owner())->withSession(['auth.password_confirmed_at' => time()])
            ->postJson('/operator/products/draft', ['name' => 'KMJ Draft Workspace', 'category' => 'developer'])
            ->assertOk()->assertJsonPath('provider', 'verified-free-cloud')
            ->assertJsonPath('draft.summary', 'A proposed engineering workspace.')
            ->assertJsonMissingPath('draft.purchase_enabled');
        Http::assertSent(fn ($request): bool => str_ends_with($request->url(), '/chat/completions') && $request['max_tokens'] === 8000 && $request['response_format']['type'] === 'json_schema');
        self::assertSame(0, Product::query()->count());
    }

    public function test_paid_model_configuration_never_receives_product_data(): void
    {
        Http::preventStrayRequests();
        config(['product_studio.text.enabled' => true, 'product_studio.text.api_key' => 'test-only-not-a-key', 'product_studio.text.model' => 'paid-model']);
        $this->actingAs($this->owner())->withSession(['auth.password_confirmed_at' => time()])
            ->postJson('/operator/products/draft', ['name' => 'KMJ Test'])->assertStatus(503);
        Http::assertNothingSent();
    }

    public function test_full_product_copy_persists_and_uses_existing_public_metadata(): void
    {
        $this->actingAs($this->owner())->withSession(['auth.password_confirmed_at' => time()]);
        $this->post('/operator/products', [
            'name' => 'KMJ Full Product', 'slug' => 'kmj-full-product',
            'category' => 'developer', 'lifecycle' => 'planned',
            'is_public' => true, 'purchase_enabled' => false, 'licensing_enabled' => false,
            'summary' => 'Owner-reviewed summary.',
            'content' => ['headline' => 'Owner-reviewed headline', 'description' => 'Longer product copy.',
                'features' => ['Reviewed feature'], 'faqs' => [['question' => 'What is it?', 'answer' => 'A planned product.']]],
        ])->assertSessionHasNoErrors()->assertRedirect();
        $product = Product::query()->where('slug', 'kmj-full-product')->firstOrFail();
        self::assertSame('Owner-reviewed headline', $product->content['headline']);
        $this->get('/products/kmj-full-product')->assertInertia(fn (Assert $page) => $page
            ->component('products/show')
            ->where('product.headline', 'Owner-reviewed headline')
            ->where('product.summary', 'Owner-reviewed summary.')
            ->where('product.content.features.0', 'Reviewed feature')
            ->where('product.purchase_enabled', false));
    }

    public function test_invalid_content_and_svg_upload_are_rejected(): void
    {
        $this->actingAs($this->owner())->withSession(['auth.password_confirmed_at' => time()]);
        $this->postJson('/operator/products/media', [
            'image' => UploadedFile::fake()->createWithContent('unsafe.svg', '<svg onload="alert(1)"/>'),
        ])->assertUnprocessable();
        $this->post('/operator/products', [
            'name' => 'KMJ Bad Content', 'slug' => 'kmj-bad-content', 'lifecycle' => 'planned',
            'is_public' => false, 'purchase_enabled' => false, 'licensing_enabled' => false,
            'content' => ['description' => str_repeat('x', 20001)],
        ])->assertSessionHasErrors('content.description');
        self::assertSame(0, Product::query()->count());
    }

    public function test_uploaded_artwork_is_private_until_attached_to_a_public_product(): void
    {
        Storage::fake('local');
        $this->actingAs($this->owner())->withSession(['auth.password_confirmed_at' => time()]);
        $binary = base64_decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=', true);
        $response = $this->postJson('/operator/products/media', [
            'image' => UploadedFile::fake()->createWithContent('product.png', $binary),
            'variant' => 'photo',
        ])->assertOk()->assertJsonPath('provider', 'owner-upload')->assertJsonPath('product_saved', false);
        $path = $response->json('path');
        $this->get($path)->assertOk()->assertHeader('Content-Type', 'image/png');
        $this->actingAs(User::factory()->create(['email_verified_at' => now()]));
        $this->get($path)->assertForbidden();
        Product::query()->create(['slug' => 'kmj-media-test', 'name' => 'Media test', 'status' => 'sandbox', 'lifecycle' => 'planned', 'is_public' => true, 'image_path' => $path]);
        $this->get($path)->assertOk()->assertHeader('X-Content-Type-Options', 'nosniff');
    }

    public function test_unknown_price_never_reaches_cloud_completion(): void
    {
        config(['product_studio.text.enabled' => true, 'product_studio.text.api_key' => 'test-only-not-a-key', 'product_studio.text.model' => 'openrouter/free']);
        Http::fake(['openrouter.ai/api/v1/models' => Http::response(['data' => [['id' => 'openrouter/free', 'pricing' => ['prompt' => '0']]]])]);
        $this->actingAs($this->owner())->withSession(['auth.password_confirmed_at' => time()])
            ->postJson('/operator/products/draft', ['name' => 'KMJ Invalid Draft'])->assertStatus(503);
        Http::assertNotSent(fn ($request): bool => str_ends_with($request->url(), '/chat/completions'));
        self::assertSame(0, Product::query()->count());
    }

    public function test_free_suffix_with_nonzero_price_never_calls_completion(): void
    {
        config(['product_studio.text.enabled' => true, 'product_studio.text.api_key' => 'test-only-not-a-key', 'product_studio.text.model' => 'vendor/model:free']);
        Http::fake(['openrouter.ai/api/v1/models' => Http::response(['data' => [['id' => 'vendor/model:free', 'pricing' => ['prompt' => '0.001', 'completion' => '0']]]])]);
        $this->actingAs($this->owner())->withSession(['auth.password_confirmed_at' => time()])
            ->postJson('/operator/products/draft', ['name' => 'KMJ Price Guard'])->assertStatus(503);
        Http::assertNotSent(fn ($request): bool => str_ends_with($request->url(), '/chat/completions'));
    }

    public function test_cloud_quota_error_stops_without_paid_retry_and_cools_down(): void
    {
        config(['product_studio.text.enabled' => true, 'product_studio.text.api_key' => 'test-only-not-a-key', 'product_studio.text.model' => 'openrouter/free']);
        Http::fake(['openrouter.ai/api/v1/models' => Http::response(['data' => [['id' => 'openrouter/free', 'pricing' => ['prompt' => '0', 'completion' => '0']]]]),
            'openrouter.ai/api/v1/chat/completions' => Http::response(['error' => 'quota'], 429)]);
        $this->actingAs($this->owner())->withSession(['auth.password_confirmed_at' => time()]);
        $this->postJson('/operator/products/draft', ['name' => 'KMJ Quota Guard'])->assertStatus(429)->assertJsonPath('code', 'FREE_CLOUD_RATE_LIMITED')->assertHeader('Retry-After', '60');
        $this->postJson('/operator/products/draft', ['name' => 'KMJ Quota Guard'])->assertStatus(429)->assertJsonPath('code', 'FREE_CLOUD_RATE_LIMITED')->assertHeader('Retry-After');
        Http::assertSentCount(2);
        Http::assertSent(fn ($request): bool => str_ends_with($request->url(), '/chat/completions')
            && $request['model'] === 'openrouter/free'
            && $request['provider']['max_price']['prompt'] === 0
            && $request['provider']['max_price']['completion'] === 0
            && $request['provider']['allow_fallbacks'] === false);
    }

    public function test_length_stopped_response_is_rejected_even_if_its_json_is_valid(): void
    {
        config(['product_studio.text.enabled' => true, 'product_studio.text.api_key' => 'test-only-not-a-key', 'product_studio.text.model' => 'openrouter/free']);
        Http::fake(['openrouter.ai/api/v1/models' => Http::response(['data' => [['id' => 'openrouter/free', 'pricing' => ['prompt' => '0', 'completion' => '0']]]]),
            'openrouter.ai/api/v1/chat/completions' => Http::response(['usage' => ['cost' => 0], 'choices' => [['finish_reason' => 'length', 'message' => ['content' => json_encode([
                'summary' => 'Proposed draft', 'headline' => 'Proposed headline', 'description' => 'Proposed description', 'features' => [], 'faqs' => [], 'photo_prompt' => 'Product photo', 'banner_prompt' => 'Product banner',
            ], JSON_THROW_ON_ERROR)]]]])]);
        $this->actingAs($this->owner())->withSession(['auth.password_confirmed_at' => time()])
            ->postJson('/operator/products/draft', ['name' => 'KMJ Truncated Draft'])
            ->assertStatus(422)->assertJsonPath('code', 'CLOUD_DRAFT_INCOMPLETE')->assertJsonMissingPath('draft');
        self::assertSame(0, Product::query()->count());
    }

    public function test_one_click_ai_creation_saves_complete_private_draft_and_blocks_duplicate(): void
    {
        config(['product_studio.text.enabled' => true, 'product_studio.text.api_key' => 'test-only-not-a-key', 'product_studio.text.model' => 'openrouter/free']);
        Http::fake(['openrouter.ai/api/v1/models' => Http::response(['data' => [['id' => 'openrouter/free', 'pricing' => ['prompt' => '0', 'completion' => '0']]]]),
            'openrouter.ai/api/v1/chat/completions' => Http::response(['usage' => ['cost' => 0], 'choices' => [['finish_reason' => 'stop', 'message' => ['content' => json_encode([
                'summary' => 'Proposed engineering service.', 'headline' => 'Engineering support', 'description' => 'Proposed service scope for owner review.', 'features' => ['Proposed consultation'], 'faqs' => [['question' => 'Is it available?', 'answer' => 'Availability is not verified.']], 'photo_prompt' => 'Engineering workspace', 'banner_prompt' => 'Wide engineering workspace',
            ], JSON_THROW_ON_ERROR)]]]])]);
        $this->actingAs($this->owner())->withSession(['auth.password_confirmed_at' => time()]);
        $payload = ['name' => 'KMJ Engineering Service', 'category' => 'industrial', 'offering_type' => 'service', 'context' => 'Proposed engineering service.', 'is_public' => true, 'purchase_enabled' => true, 'licensing_enabled' => true, 'lifecycle' => 'available'];
        $this->postJson('/operator/products/ai-create', $payload)->assertCreated()->assertJsonPath('saved', true)->assertJsonPath('product.slug', 'kmj-engineering-service');
        $product = Product::query()->sole();
        self::assertFalse($product->is_public);
        self::assertFalse($product->purchase_enabled);
        self::assertFalse($product->licensing_enabled);
        self::assertSame('planned', $product->lifecycle);
        self::assertSame('service', $product->content['offering_type']);
        self::assertSame('Engineering support', $product->content['headline']);
        self::assertNotEmpty($product->content['image_alt']);
        self::assertSame('Proposed engineering service.', $product->summary);
        $this->get('/products/'.$product->slug)->assertNotFound();
        $this->postJson('/operator/products/ai-create', $payload)->assertUnprocessable();
        self::assertSame(1, Product::query()->count());
        Http::assertSentCount(2);
    }

    public function test_one_click_ai_creation_requires_owner_and_never_saves_failed_generation(): void
    {
        Http::preventStrayRequests();
        $this->postJson('/operator/products/ai-create', ['name' => 'KMJ Test'])->assertUnauthorized();
        $this->actingAs(User::factory()->create(['email_verified_at' => now()]))->withSession(['auth.password_confirmed_at' => time()])
            ->postJson('/operator/products/ai-create', ['name' => 'KMJ Test'])->assertForbidden();
        $this->actingAs($this->owner())->withSession(['auth.password_confirmed_at' => time()]);
        config(['product_studio.text.enabled' => false]);
        $this->postJson('/operator/products/ai-create', ['name' => 'KMJ Test', 'category' => 'other', 'offering_type' => 'product'])->assertStatus(503);
        self::assertSame(0, Product::query()->count());
        Http::assertNothingSent();
    }

    public function test_existing_metadata_uses_service_schema_and_only_visible_faqs(): void
    {
        $metadata = app(PublicInitialMetadata::class)->forPage(['component' => 'products/show', 'props' => ['product' => [
            'slug' => 'kmj-engineering', 'name' => 'KMJ Engineering', 'summary' => 'Proposed engineering service.', 'lifecycle_label' => 'Planned',
            'image_path' => '/assets/brand/kmj-social-card.webp', 'content' => ['offering_type' => 'service', 'faqs' => [['question' => 'What is it?', 'answer' => 'A proposed service.']]],
        ]]], 'https://kmjtechno.com');
        $schema = json_decode($metadata['json_ld'], true, 32, JSON_THROW_ON_ERROR);
        self::assertSame('Service', $schema[0]['@type']);
        self::assertSame('FAQPage', $schema[1]['@type']);
        self::assertSame('A proposed service.', $schema[1]['mainEntity'][0]['acceptedAnswer']['text']);
        self::assertStringNotContainsString('aggregateRating', $metadata['json_ld']);
        self::assertSame('https://kmjtechno.com/products/kmj-engineering', $metadata['canonical']);
    }

    private function owner(): User
    {
        $owner = User::factory()->create([
            'email_verified_at' => now(),
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ]);
        DB::table('passkeys')->insert([
            'user_id' => $owner->id,
            'name' => 'Product owner passkey',
            'credential_id' => 'product-owner-'.Str::uuid(),
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $owner;
    }
}
