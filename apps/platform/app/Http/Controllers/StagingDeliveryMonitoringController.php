<?php

namespace App\Http\Controllers;

use App\Services\Operations\DeliveryControlSnapshot;
use Illuminate\Http\JsonResponse;
use Inertia\Inertia;
use Inertia\Response;

final class StagingDeliveryMonitoringController extends Controller
{
    public function index(StagingMonitoringController $telemetry): Response
    {
        // Reuse the existing exact-host/environment guard without duplicating it.
        $telemetry->index();

        return Inertia::render('info-control', [
            'pollIntervalMs' => 5000,
        ]);
    }

    public function status(
        StagingMonitoringController $telemetry,
        DeliveryControlSnapshot $delivery,
    ): JsonResponse {
        $response = $telemetry->status();
        $payload = $response->getData(true);
        $payload['delivery'] = $delivery->capture();

        return response()->json($payload, $response->getStatusCode());
    }
}
