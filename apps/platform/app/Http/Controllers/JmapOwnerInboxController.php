<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Models\User;
use App\Services\Mail\JmapOwnerPilot;
use App\Services\PlatformOwnerAccess;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use RuntimeException;

final class JmapOwnerInboxController
{
    public function __invoke(Request $request, PlatformOwnerAccess $access, JmapOwnerPilot $pilot): JsonResponse
    {
        $headers = ['Cache-Control' => 'private, no-store, max-age=0', 'Pragma' => 'no-cache'];
        $actor = $request->user();
        if (! $actor instanceof User || ! $access->allows($actor)
            || config('kmj-mail-engine.pilot_enabled') !== true
            || $actor->getKey() !== config('kmj-mail-engine.pilot_owner_id')) {
            return response()->json(['status' => 'unavailable'], 403, $headers);
        }

        // The only caller-controlled value is an integer page position.
        $input = $request->except('_token');
        $position = $input['position'] ?? 0;
        if (array_diff(array_keys($input), ['position']) !== []
            || ! is_int($position) || $position < 0 || $position > 40000) {
            return response()->json(['status' => 'invalid_position'], 422, $headers);
        }

        try {
            $summary = $pilot->inboxSummary($actor, $position);
        } catch (RuntimeException) {
            // Never log or return the underlying provider response or credential.
            return response()->json(['status' => 'unavailable'], 503, $headers);
        }

        return response()->json(['status' => 'available', 'inbox' => $summary], 200, $headers);
    }
}
