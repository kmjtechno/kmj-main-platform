<?php

namespace App\Services\Operations;

use App\Models\OperatorActionAudit;
use App\Models\User;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;
use RuntimeException;

/**
 * One protected action: dispatch the fixed main-only CodeBridge staging
 * workflow. Neither web input nor an environment value chooses the workflow,
 * Git ref, repository, script, command or destination host.
 */
final class CodeBridgeStageDispatcher
{
    private const API = 'https://api.github.com/repos/kmjtechno/kmj-codebridge';

    private const WORKFLOW = 'oneclick-stage.yml';

    private const GUARD_KEY = 'kmj-codebridge-stage:owner-v1';

    /** @return array{status: string, configured: bool, workflow_url: string} */
    public function snapshot(): array
    {
        return [
            'status' => $this->token() === '' ? 'NOT_CONFIGURED' : 'READY_TO_REQUEST',
            'configured' => $this->token() !== '',
            'workflow_url' => 'https://github.com/kmjtechno/kmj-codebridge/actions/workflows/oneclick-stage.yml',
        ];
    }

    /**
     * @return array{status: string, sha: string}
     */
    public function request(User $owner): array
    {
        $token = $this->token();
        if ($token === '') {
            throw new RuntimeException('STAGE_GITHUB_CONNECTOR_NOT_CONFIGURED');
        }
        // A true cache-store atomic add rate-limits repeated clicks across PHP
        // workers. Ambiguous outbound results must not trigger blind retry.
        if (! Cache::add(self::GUARD_KEY, 1, now()->addMinutes(2))) {
            throw new RuntimeException('STAGE_REQUEST_ALREADY_PENDING');
        }

        $posted = false;
        try {
            $client = Http::withToken($token)
                ->acceptJson()
                ->withHeaders(['X-GitHub-Api-Version' => '2022-11-28'])
                ->timeout(10);
            $source = $client->get(self::API.'/commits/main');
            $sha = $source->json('sha');
            if (! $source->ok() || ! is_string($sha) ||
                preg_match('/\A[a-f0-9]{40}\z/D', $sha) !== 1) {
                throw new RuntimeException('STAGE_SOURCE_IDENTITY_UNVERIFIED');
            }

            $runs = $client->get(self::API.'/actions/workflows/'.self::WORKFLOW.'/runs', [
                'branch' => 'main',
                'event' => 'workflow_dispatch',
                'per_page' => 10,
            ]);
            if (! $runs->ok() || ! is_array($runs->json('workflow_runs'))) {
                throw new RuntimeException('STAGE_RUNS_IDENTITY_UNVERIFIED');
            }
            foreach ($runs->json('workflow_runs') as $run) {
                if (! is_array($run) || ! isset($run['head_sha'], $run['status'])) {
                    throw new RuntimeException('STAGE_RUN_RECEIPT_MALFORMED');
                }
                if ($run['head_sha'] === $sha &&
                    in_array($run['status'], ['queued', 'in_progress', 'waiting', 'requested', 'pending'], true)) {
                    throw new RuntimeException('STAGE_RUN_ALREADY_ACTIVE');
                }
            }

            // Persist a durable owner audit BEFORE sending the irreversible
            // external request. HTTP 204 only means GitHub accepted dispatch.
            $audit = OperatorActionAudit::query()->create([
                'actor_user_id' => $owner->getKey(),
                'action' => 'codebridge.stage',
                'outcome' => 'requested',
                'metadata' => [
                    'repository' => 'kmjtechno/kmj-codebridge',
                    'workflow' => self::WORKFLOW,
                    'source_sha' => $sha,
                    'signed' => false,
                    'production_mutation' => false,
                ],
            ]);
            $posted = true;
            try {
                $response = $client->post(self::API.'/actions/workflows/'.self::WORKFLOW.'/dispatches', [
                    'ref' => 'main',
                ]);
                $audit->update(['outcome' => $response->status() === 204 ? 'queued' : 'unknown']);
                if ($response->status() !== 204) {
                    throw new RuntimeException('STAGE_DISPATCH_NOT_ACKNOWLEDGED');
                }
            } catch (RuntimeException $exception) {
                throw $exception;
            } catch (\Throwable $exception) {
                $audit->update(['outcome' => 'unknown']);
                throw new RuntimeException('STAGE_DISPATCH_OUTCOME_UNKNOWN', 0, $exception);
            }

            return ['status' => 'REQUEST_ACCEPTED_NOT_STAGE_PROOF', 'sha' => $sha];
        } catch (\Throwable $exception) {
            // Keep cooldown on ambiguous remote POST; only pre-dispatch errors
            // may safely clear the claim.
            if (! $posted) {
                Cache::forget(self::GUARD_KEY);
            }
            if ($exception instanceof RuntimeException) {
                throw $exception;
            }
            throw new RuntimeException('STAGE_UPSTREAM_UNAVAILABLE', 0, $exception);
        }
    }

    private function token(): string
    {
        $value = config('services.codebridge_stage.github_token');

        return is_string($value) && strlen($value) <= 512 ? trim($value) : '';
    }
}
