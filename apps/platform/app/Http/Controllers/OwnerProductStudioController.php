<?php

namespace App\Http\Controllers;

use App\Models\User;
use App\Services\Commerce\AdminProductManager;
use App\Services\PlatformOwnerAccess;
use App\Services\ProductStudio\FreeCloudProductDraftGenerator;
use App\Services\ProductStudio\FreeCloudRateLimited;
use App\Services\ProductStudio\IncompleteCloudDraft;
use App\Services\ProductStudio\ProductArtworkStorage;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Facades\Validator;
use Illuminate\Support\Str;
use Illuminate\Validation\Rule;
use Illuminate\Validation\ValidationException;
use KMJ\MainPlatform\Catalog\Models\Product;
use Symfony\Component\HttpFoundation\StreamedResponse;
use Throwable;

final class OwnerProductStudioController extends Controller
{
    public function draft(Request $request, PlatformOwnerAccess $access, FreeCloudProductDraftGenerator $generator): JsonResponse
    {
        $this->authorizeOwner($request, $access);
        $data = $request->validate([
            'name' => ['required', 'string', 'min:2', 'max:160'],
            'category' => ['sometimes', 'string', 'max:60'],
            'context' => ['nullable', 'string', 'max:8000'],
        ]);
        try {
            $draft = $generator->draft($data['name'], $data['category'] ?? 'other', $data['context'] ?? '');
        } catch (IncompleteCloudDraft $error) {
            return response()->json(['code' => $error->getMessage(), 'message' => 'The cloud model returned an incomplete or invalid draft. Nothing was applied or saved. Keep your current fields and try a shorter set of public facts later.'], 422);
        } catch (FreeCloudRateLimited $error) {
            return response()->json(['code' => 'FREE_CLOUD_RATE_LIMITED', 'message' => 'The free cloud provider is rate-limited or its free quota is exhausted. Wait before retrying and check the provider quota reset. Your fields remain unchanged; manual editing is available.', 'retry_after' => $error->retryAfter], 429)->header('Retry-After', (string) $error->retryAfter);
        } catch (Throwable) {
            return response()->json(['code' => 'GENERATION_UNAVAILABLE', 'message' => 'Verified-free cloud generation is unavailable, quota-limited or returned an invalid draft. Your current fields have not changed.'], 503);
        }

        return response()->json(['draft' => $draft, 'provider' => 'verified-free-cloud', 'saved' => false]);
    }

    public function createDraft(Request $request, PlatformOwnerAccess $access, FreeCloudProductDraftGenerator $generator, AdminProductManager $manager): JsonResponse
    {
        $this->authorizeOwner($request, $access);
        $data = $request->validate([
            'name' => ['required', 'string', 'min:2', 'max:160'],
            'category' => ['required', Rule::in(AdminProductManager::CATEGORIES)],
            'offering_type' => ['required', 'in:product,service'],
            'context' => ['nullable', 'string', 'max:7900'],
        ]);
        $slug = Str::slug($data['name']);
        if ($slug === '' || strlen($slug) > 96) {
            throw ValidationException::withMessages(['name' => 'Use a shorter title with letters or numbers for its public URL.']);
        }
        $lock = Cache::lock('product-studio-create:'.$slug, 120);
        if (! $lock->get()) {
            return response()->json(['message' => 'This title is already being prepared. Wait before trying again.'], 409);
        }
        try {
            if (Product::query()->where('slug', $slug)->exists()) {
                throw ValidationException::withMessages(['name' => 'This product or service already exists. Edit its existing catalog entry.']);
            }
            $request->merge(['context' => 'Offering type: '.$data['offering_type']."\n".($data['context'] ?? '')]);
            $response = $this->draft($request, $access, $generator);
            if ($response->getStatusCode() !== 200) {
                return $response;
            }
            $draft = $response->getData(true)['draft'];
            $product = $this->saveGeneratedDraft($draft, $data, $manager);

            return response()->json(['saved' => true, 'product' => $product, 'artwork' => 'existing-brand-fallback'], 201);
        } finally {
            $lock->release();
        }
    }

    public function fromBrief(Request $request, PlatformOwnerAccess $access, FreeCloudProductDraftGenerator $generator, AdminProductManager $manager): JsonResponse
    {
        $this->authorizeOwner($request, $access);
        $data = $request->validate(['brief' => ['required', 'string', 'min:20', 'max:3000'], 'request_id' => ['required', 'uuid']]);
        $key = 'product-studio-brief:'.$request->user()?->getAuthIdentifier().':'.$data['request_id'];
        $fingerprint = hash('sha256', trim($data['brief']));
        $lock = Cache::lock($key.':lock', 120);
        if (! $lock->get()) {
            return response()->json(['message' => 'This description is already being prepared. Wait before retrying.'], 409);
        }
        try {
            $receipt = Cache::get($key);
            if (is_array($receipt)) {
                if (($receipt['fingerprint'] ?? null) !== $fingerprint) {
                    return response()->json(['message' => 'The description changed. Start a new generation action.'], 409);
                }
                $productId = $receipt['product_id'] ?? null;
                $existing = is_string($productId) ? Product::query()->find($productId) : null;
                if (! $existing) {
                    return response()->json(['message' => 'The saved draft is no longer available. Start a new generation action.'], 409);
                }

                return response()->json(['saved' => true, 'product' => $existing, 'artwork' => 'existing-brand-fallback']);
            }
            try {
                $draft = $generator->fromBrief(trim($data['brief']));
            } catch (IncompleteCloudDraft $error) {
                return response()->json(['code' => $error->getMessage(), 'message' => 'The cloud draft was incomplete. Your description is preserved and no product was saved.'], 422);
            } catch (FreeCloudRateLimited $error) {
                return response()->json(['code' => 'FREE_CLOUD_RATE_LIMITED', 'message' => 'The free provider is rate-limited. Your description is preserved; wait before retrying.', 'retry_after' => $error->retryAfter], 429)->header('Retry-After', (string) $error->retryAfter);
            } catch (Throwable) {
                return response()->json(['code' => 'GENERATION_UNAVAILABLE', 'message' => 'A complete verified-free draft could not be prepared. Your description is preserved and no product was saved.'], 503);
            }
            $slug = Str::slug($draft['name']);
            $slugLock = Cache::lock('product-studio-create:'.$slug, 120);
            if (! $slugLock->get()) {
                return response()->json(['message' => 'This product title is already being prepared. Wait before retrying.'], 409);
            }
            try {
                $identity = ['name' => $draft['name'], 'category' => $draft['category'], 'offering_type' => $draft['offering_type']];
                $product = $this->saveGeneratedDraft($draft, $identity, $manager);
                Cache::put($key, ['fingerprint' => $fingerprint, 'product_id' => (string) $product->getKey()], 3600);
            } finally {
                $slugLock->release();
            }

            return response()->json(['saved' => true, 'product' => $product, 'artwork' => 'existing-brand-fallback'], 201);
        } finally {
            $lock->release();
        }
    }

    public function media(Request $request, PlatformOwnerAccess $access, FreeCloudProductDraftGenerator $generator, ProductArtworkStorage $storage): JsonResponse
    {
        $this->authorizeOwner($request, $access);
        $data = $request->validate([
            'image' => ['nullable', 'file', 'mimes:png,jpg,jpeg,webp', 'max:8192', 'dimensions:max_width=4096,max_height=4096'],
            'prompt' => ['required_without:image', 'nullable', 'string', 'min:8', 'max:2000'],
            'variant' => ['sometimes', 'in:photo,banner'],
        ]);
        try {
            $uploaded = $request->file('image');
            $binary = $uploaded instanceof UploadedFile ? $uploaded->getContent() : $generator->image($data['prompt'], $data['variant'] ?? 'photo');
            $path = $storage->store($binary);
        } catch (Throwable) {
            return response()->json(['code' => 'ARTWORK_UNAVAILABLE', 'message' => 'Artwork could not be prepared. Use a valid PNG, JPEG or WebP, or wait until a verified-free cloud image provider is configured. Your product has not changed.'], 503);
        }

        return response()->json(['path' => $path, 'provider' => $uploaded instanceof UploadedFile ? 'owner-upload' : 'verified-free-cloud-image', 'product_saved' => false]);
    }

    public function showArtwork(Request $request, string $asset, PlatformOwnerAccess $access): StreamedResponse
    {
        abort_unless(preg_match('/^[0-9a-f-]{36}\.(png|jpg|webp)$/D', $asset) === 1, 404);
        $path = '/product-artwork/'.$asset;
        $public = Product::query()->where('is_public', true)->where(function ($query) use ($path): void {
            $query->where('image_path', $path)->orWhere('content->banner_path', $path);
        })->exists();
        if (! $public) {
            $this->authorizeOwner($request, $access);
        }
        $disk = Storage::disk('local');
        abort_unless($disk->exists('product-artwork/'.$asset), 404);
        $extension = pathinfo($asset, PATHINFO_EXTENSION);
        $type = ['png' => 'image/png', 'jpg' => 'image/jpeg', 'webp' => 'image/webp'][$extension];

        return $disk->response('product-artwork/'.$asset, null, [
            'Content-Type' => $type,
            'X-Content-Type-Options' => 'nosniff',
            'X-Robots-Tag' => 'noindex',
            'Cache-Control' => $public ? 'public, max-age=3600' : 'private, no-store',
            'Content-Security-Policy' => "default-src 'none'; sandbox",
        ]);
    }

    /**
     * @param  array<string, mixed>  $draft
     * @param  array<string, mixed>  $data
     */
    private function saveGeneratedDraft(array $draft, array $data, AdminProductManager $manager): Product
    {
        $slug = Str::slug($data['name']);
        $content = array_intersect_key($draft, array_flip(['headline', 'description', 'features', 'faqs', 'photo_prompt', 'banner_prompt']));
        $content['offering_type'] = $data['offering_type'];
        $content['image_alt'] = 'KMJ TECHNO brand artwork for '.$data['name'];
        $content['banner_path'] = '/assets/brand/kmj-social-card.webp';
        $attributes = [
            'name' => $data['name'], 'slug' => $slug, 'category' => $data['category'],
            'summary' => $draft['summary'], 'content' => $content,
            'image_path' => '/assets/brand/kmj-social-card.webp',
            'lifecycle' => 'planned', 'is_public' => false, 'purchase_enabled' => false, 'licensing_enabled' => false,
        ];
        $validated = Validator::make($attributes, AdminProductManager::rules())->validate();

        return $manager->create($validated);
    }

    private function authorizeOwner(Request $request, PlatformOwnerAccess $access): void
    {
        $user = $request->user();
        abort_unless($user instanceof User, 401);
        $access->require($user);
    }
}
