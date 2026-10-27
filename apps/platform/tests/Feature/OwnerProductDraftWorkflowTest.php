<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\UploadedFile;
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
            'usage' => ['cost' => 0], 'choices' => [['message' => ['content' => json_encode([
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
