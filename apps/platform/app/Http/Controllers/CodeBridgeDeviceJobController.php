<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Services\CodeBridge\Workspace\WorkspaceJobService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use InvalidArgumentException;
use RuntimeException;
use Symfony\Component\HttpKernel\Exception\HttpExceptionInterface;

/**
 * Device-agent facing queue API. Authenticates with the device's existing bearer credential
 * (same one used for lease renewal) and a per-job claim token. It can only hand out approved
 * named tools that a signed-in user queued for this exact device and project.
 */
final class CodeBridgeDeviceJobController
{
    public function __construct(private readonly WorkspaceJobService $jobs) {}

    public function claim(Request $request): JsonResponse
    {
        $this->guard($request, 1024);
        [$tenant, $device] = $this->device($request);
        $job = $this->jobs->claim($tenant, $device);

        return $this->json($job === null ? ['job' => null] : ['job' => $job]);
    }

    public function report(Request $request, string $job): JsonResponse
    {
        $this->guard($request, 16384);
        [$tenant, $device] = $this->device($request);
        $claim = $request->header('X-KMJ-Claim');
        if (! is_string($claim) || preg_match('/\A[0-9a-f]{48}\z/', $claim) !== 1) {
            abort(401);
        }
        try {
            return $this->json($this->jobs->report($tenant, $device, $job, $claim, $request->json()->all()));
        } catch (HttpExceptionInterface $exception) {
            throw $exception;
        } catch (InvalidArgumentException $exception) {
            return $this->json(['error' => $exception->getMessage()], 422);
        } catch (RuntimeException $exception) {
            return $this->json(['error' => $exception->getMessage()], 409);
        }
    }

    private function guard(Request $request, int $maxBytes): void
    {
        if (! config('codebridge.enabled', false) || ! WorkspaceJobService::enabled()) {
            abort(503);
        }
        if (strlen($request->getContent()) > $maxBytes) {
            abort(413);
        }
    }

    /** @return array{0: string, 1: string} */
    private function device(Request $request): array
    {
        $credential = $request->bearerToken();
        if (! is_string($credential) || strlen($credential) < 32 || strlen($credential) > 4096) {
            abort(401);
        }
        $row = DB::table('codebridge_device_credentials as c')
            ->join('kslp_activations as a', 'a.id', '=', 'c.activation_id')
            ->join('kslp_licenses as l', 'l.id', '=', 'c.license_id')
            ->where('c.token_hash', hash('sha256', $credential))
            ->whereNull('c.revoked_at')->where('c.expires_at_epoch', '>', time())
            ->whereColumn('a.license_id', 'l.id')
            ->whereNull('a.deactivated_at')
            ->where('l.product', 'KMJ_CODEBRIDGE')->where('l.status', 'active')
            ->whereNull('l.revoked_at')->where('l.starts_at', '<=', now())
            ->where('l.expires_at', '>', now())
            ->first(['c.tenant_id', 'c.device_id']);
        if ($row === null) {
            abort(401);
        }
        $fields = (array) $row;

        return [(string) $fields['tenant_id'], (string) $fields['device_id']];
    }

    /** @param array<string, mixed> $payload */
    private function json(array $payload, int $status = 200): JsonResponse
    {
        return response()->json($payload, $status)->header('Cache-Control', 'no-store, private');
    }
}
