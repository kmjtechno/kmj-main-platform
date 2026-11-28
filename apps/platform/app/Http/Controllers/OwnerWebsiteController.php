<?php

namespace App\Http\Controllers;

use App\Models\User;
use App\Services\PlatformOwnerAccess;
use App\Services\Website\WebsiteSettings;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;
use Illuminate\Validation\ValidationException;
use Inertia\Inertia;
use Inertia\Response;
use Symfony\Component\HttpFoundation\StreamedResponse;

final class OwnerWebsiteController extends Controller
{
    private const PHOTO_PATH = '#^/team-photo/[0-9a-f-]{36}\.(png|jpg|webp)$#D';

    public function index(Request $request, PlatformOwnerAccess $access, WebsiteSettings $website): Response
    {
        $this->owner($request, $access);

        return Inertia::render('operator-website', [
            'settings' => $website->all(),
            'ready' => $website->available(),
        ]);
    }

    public function updateSite(Request $request, PlatformOwnerAccess $access, WebsiteSettings $website): RedirectResponse
    {
        $user = $this->owner($request, $access);
        $this->requireStorage($website);

        $rules = [
            'features' => ['required', 'array'],
            'sections' => ['required', 'array'],
            'headings' => ['required', 'array'],
            'roadmap' => ['required', 'array', 'size:4'],
            'roadmap.*.title' => ['required', 'string', 'max:40'],
            'roadmap.*.summary' => ['required', 'string', 'max:120'],
            'roadmap.*.text' => ['required', 'string', 'max:240'],
        ];
        foreach (array_keys(WebsiteSettings::defaults()['features']) as $feature) {
            $rules['features.'.$feature] = ['required', 'boolean'];
        }
        foreach (WebsiteSettings::SECTIONS as $section) {
            $rules['sections.'.$section] = ['required', 'boolean'];
        }
        foreach (WebsiteSettings::HEADINGS as $heading) {
            $rules['headings.'.$heading.'.title'] = ['required', 'string', 'max:80'];
            $rules['headings.'.$heading.'.subtitle'] = ['required', 'string', 'max:200'];
        }
        $data = $request->validate($rules);

        $website->save([
            'features' => array_map(boolval(...), $data['features']),
            'sections' => array_map(boolval(...), $data['sections']),
            'headings' => $data['headings'],
            'roadmap' => array_values($data['roadmap']),
        ], (int) $user->getAuthIdentifier());

        return back()->with('success', 'Website settings saved.');
    }

    public function updateTeam(Request $request, PlatformOwnerAccess $access, WebsiteSettings $website): RedirectResponse
    {
        $user = $this->owner($request, $access);
        $this->requireStorage($website);

        $data = $request->validate([
            'published' => ['required', 'boolean'],
            'intro' => ['nullable', 'string', 'max:300'],
            'members' => ['present', 'array', 'max:40'],
            'members.*.name' => ['required', 'string', 'max:120'],
            'members.*.role' => ['required', 'string', 'max:120'],
            'members.*.bio' => ['nullable', 'string', 'max:400'],
            'members.*.photo' => ['nullable', 'string', 'regex:'.self::PHOTO_PATH],
            'members.*.linkedin' => ['nullable', 'string', 'max:200', 'regex:#^https://([a-z]{2,3}\.)?linkedin\.com/[^\s]*$#D'],
            'members.*.visible' => ['required', 'boolean'],
        ]);

        $website->save(['team' => [
            'published' => (bool) $data['published'],
            'intro' => (string) ($data['intro'] ?? ''),
            'members' => array_values(array_map(static fn (array $member): array => [
                'name' => $member['name'],
                'role' => $member['role'],
                'bio' => $member['bio'] ?? null,
                'photo' => $member['photo'] ?? null,
                'linkedin' => $member['linkedin'] ?? null,
                'visible' => (bool) $member['visible'],
            ], $data['members'])),
        ]], (int) $user->getAuthIdentifier());

        return back()->with('success', 'Team page saved.');
    }

    public function uploadPhoto(Request $request, PlatformOwnerAccess $access): JsonResponse
    {
        $this->owner($request, $access);
        $request->validate([
            'photo' => ['required', 'file', 'mimes:png,jpg,jpeg,webp', 'max:4096', 'dimensions:max_width=4096,max_height=4096'],
        ]);
        $file = $request->file('photo');
        $extension = ['image/png' => 'png', 'image/jpeg' => 'jpg', 'image/webp' => 'webp'][(string) $file->getMimeType()] ?? null;
        if ($extension === null) {
            throw ValidationException::withMessages(['photo' => 'Use a PNG, JPEG or WebP image.']);
        }
        $name = Str::uuid().'.'.$extension;
        abort_unless(Storage::disk('local')->put('team-photos/'.$name, $file->getContent()), 503, 'Photo could not be saved.');

        return response()->json(['path' => '/team-photo/'.$name], 201);
    }

    public function showPhoto(Request $request, string $asset, PlatformOwnerAccess $access, WebsiteSettings $website): StreamedResponse
    {
        abort_unless(preg_match('/^[0-9a-f-]{36}\.(png|jpg|webp)$/D', $asset) === 1, 404);
        $public = $website->isPublicPhoto('/team-photo/'.$asset);
        if (! $public) {
            $this->owner($request, $access);
        }
        $disk = Storage::disk('local');
        abort_unless($disk->exists('team-photos/'.$asset), 404);
        $type = ['png' => 'image/png', 'jpg' => 'image/jpeg', 'webp' => 'image/webp'][pathinfo($asset, PATHINFO_EXTENSION)];

        return $disk->response('team-photos/'.$asset, null, [
            'Content-Type' => $type,
            'X-Content-Type-Options' => 'nosniff',
            'Cache-Control' => $public ? 'public, max-age=3600' : 'private, no-store',
            'Content-Security-Policy' => "default-src 'none'; sandbox",
        ]);
    }

    /** The public team page. Until published, only the owner can preview it. */
    public function team(Request $request, PlatformOwnerAccess $access, WebsiteSettings $website): Response
    {
        $team = $website->all()['team'];
        $user = $request->user();
        $preview = ! $team['published'];
        abort_if($preview && ! ($user instanceof User && $access->allows($user)), 404);

        return Inertia::render('team', [
            'intro' => $team['intro'],
            'members' => collect($team['members'])
                ->filter(fn (array $member): bool => (bool) ($member['visible'] ?? false))
                ->values()
                ->all(),
            'preview' => $preview,
        ]);
    }

    private function owner(Request $request, PlatformOwnerAccess $access): User
    {
        $user = $request->user();
        abort_unless($user instanceof User, 401);
        $access->require($user);

        return $user;
    }

    private function requireStorage(WebsiteSettings $website): void
    {
        if (! $website->available()) {
            throw ValidationException::withMessages([
                'website' => 'Saving is not ready yet: the release database step has not been run.',
            ]);
        }
    }
}
