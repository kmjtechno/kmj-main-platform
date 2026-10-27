<?php

namespace App\Http\Controllers;

use App\Models\User;
use App\Services\PlatformOwnerAccess;
use App\Services\ProductStudio\FreeCloudProductDraftGenerator;
use App\Services\ProductStudio\FreeCloudRateLimited;
use App\Services\ProductStudio\ProductArtworkStorage;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Storage;
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
        } catch (FreeCloudRateLimited $error) {
            return response()->json(['code' => 'FREE_CLOUD_RATE_LIMITED', 'message' => 'The free cloud provider is rate-limited or its free quota is exhausted. Wait before retrying and check the provider quota reset. Your fields remain unchanged; manual editing is available.', 'retry_after' => $error->retryAfter], 429)->header('Retry-After', (string) $error->retryAfter);
        } catch (Throwable) {
            return response()->json(['code' => 'GENERATION_UNAVAILABLE', 'message' => 'Verified-free cloud generation is unavailable, quota-limited or returned an invalid draft. Your current fields have not changed.'], 503);
        }

        return response()->json(['draft' => $draft, 'provider' => 'verified-free-cloud', 'saved' => false]);
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

    private function authorizeOwner(Request $request, PlatformOwnerAccess $access): void
    {
        $user = $request->user();
        abort_unless($user instanceof User, 401);
        $access->require($user);
    }
}
