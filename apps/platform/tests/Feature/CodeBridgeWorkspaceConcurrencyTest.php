<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\AiProvider;
use App\Services\AiProviders\EndpointGuard;
use App\Services\CodeBridge\Workspace\WorkspaceChatService;
use App\Services\CodeBridge\Workspace\WorkspaceConversation;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;
use RuntimeException;
use Tests\TestCase;
use Throwable;

/**
 * Real overlap on PostgreSQL: separate PROCESSES with separate connections race to send or
 * retry in one conversation. Exactly one may reserve and call the provider; the rest must be
 * refused as busy. Skipped (never faked) where PostgreSQL or pcntl is unavailable.
 */
final class CodeBridgeWorkspaceConcurrencyTest extends TestCase
{
    use RefreshDatabase;

    /** Data must be committed so forked connections can see it; the test cleans up itself. */
    protected array $connectionsToTransact = [];

    private const MODEL = 'llama-3.1-8b-instant';

    private const PROCESSES = 6;

    public function test_overlapping_sends_and_retries_reserve_one_provider_call(): void
    {
        if (DB::connection()->getDriverName() !== 'pgsql') {
            $this->markTestSkipped('Requires a real PostgreSQL connection.');
        }
        if (! function_exists('pcntl_fork') || ! function_exists('posix_kill')) {
            $this->markTestSkipped('Requires pcntl and posix.');
        }
        config()->set('ai_providers.free_models.groq', [self::MODEL]);
        $this->app->instance(EndpointGuard::class, new EndpointGuard(fn (): array => ['93.184.216.34']));

        $org = (string) Str::uuid();
        $conversationId = (string) Str::uuid();
        DB::table('organizations')->insert(['id' => $org, 'name' => 'Concurrency '.$org, 'created_at' => now(), 'updated_at' => now()]);
        $provider = new AiProvider;
        $provider->forceFill([
            'organization_id' => $org, 'name' => 'Groq race', 'preset' => 'groq', 'kind' => 'openai-compatible',
            'base_url' => 'https://api.groq.com/openai/v1', 'api_key' => 'gsk_test_0123456789abcdef', 'key_last4' => 'cdef',
            'enabled' => true, 'free_only' => true, 'health' => 'ok', 'models_cache' => [self::MODEL], 'models_checked_at' => now(),
        ])->save();
        DB::table('codebridge_workspace_conversations')->insert([
            'id' => $conversationId, 'tenant_id' => $org, 'device_id' => 'race-device', 'project_id' => 'race-project',
            'user_id' => 1, 'title' => 'Race', 'created_at' => now(), 'updated_at' => now(),
        ]);
        $conversation = new WorkspaceConversation($conversationId, $org, 'race-device', 'race-project', 1, 'Race');

        try {
            // A: overlapping sends.
            $sends = $this->overlap($conversation, $provider->id, null);
            self::assertSame(1, count(array_keys($sends['codes'], 0, true)), 'exactly one send reserves: '.json_encode($sends['codes']));
            self::assertSame(self::PROCESSES - 1, count(array_keys($sends['codes'], 3, true)), 'the rest are refused as busy: '.json_encode($sends['codes']));
            self::assertSame(1, $sends['calls'], 'one provider invocation for overlapping sends');
            self::assertSame(1, DB::table('codebridge_workspace_messages')->where('conversation_id', $conversationId)->where('role', 'user')->count());
            self::assertSame(1, DB::table('codebridge_workspace_messages')->where('conversation_id', $conversationId)->where('role', 'assistant')->count());

            // B: overlapping retries of the newest failed attempt.
            $failed = (string) DB::table('codebridge_workspace_messages')->where('role', 'assistant')->where('conversation_id', $conversationId)->value('id');
            DB::table('codebridge_workspace_messages')->where('id', $failed)->update(['status' => 'failed', 'error_code' => 'rate_limited', 'content' => '']);
            $retries = $this->overlap($conversation, $provider->id, $failed);
            self::assertSame(1, count(array_keys($retries['codes'], 0, true)), 'exactly one retry reserves: '.json_encode($retries['codes']));
            self::assertSame(1, $retries['calls'], 'one provider invocation for overlapping retries');
            self::assertSame(2, DB::table('codebridge_workspace_messages')->where('conversation_id', $conversationId)->where('role', 'assistant')->count());
            self::assertSame(1, DB::table('codebridge_workspace_messages')->where('conversation_id', $conversationId)->where('role', 'user')->count());
        } finally {
            DB::table('codebridge_workspace_conversations')->where('id', $conversationId)->delete();
            DB::table('ai_providers')->where('organization_id', $org)->delete();
            DB::table('organizations')->where('id', $org)->delete();
        }
    }

    /**
     * @return array{codes: list<int>, calls: int}  codes: 0 reserved, 3 busy, 4 other refusal, 5/9 error
     */
    private function overlap(WorkspaceConversation $conversation, string $providerId, ?string $retryOf): array
    {
        $dir = sys_get_temp_dir().'/kmj-ws-race-'.bin2hex(random_bytes(6));
        mkdir($dir, 0700);
        DB::purge(); // no connection may be shared across fork()
        $pids = [];
        for ($i = 0; $i < self::PROCESSES; $i++) {
            $pid = pcntl_fork();
            self::assertNotSame(-1, $pid, 'fork failed');
            if ($pid === 0) {
                $code = 9;
                try {
                    while (! file_exists($dir.'/go')) {
                        usleep(1000);
                    }
                    Http::fake(function () use ($dir) {
                        file_put_contents($dir.'/calls', "1\n", FILE_APPEND | LOCK_EX);
                        usleep(800000); // keep the first request in flight so the others overlap it

                        return Http::response(['choices' => [['message' => ['content' => 'ok']]]], 200);
                    });
                    $service = app(WorkspaceChatService::class);
                    try {
                        $retryOf === null
                            ? $service->send($conversation, 'hello', $providerId, self::MODEL)
                            : $service->retry($conversation, $retryOf, $providerId, self::MODEL);
                        $code = 0;
                    } catch (RuntimeException $exception) {
                        $code = $exception->getMessage() === 'conversation_busy' ? 3 : 4;
                    }
                } catch (Throwable) {
                    $code = 5;
                }
                file_put_contents($dir.'/result-'.$i, (string) $code);
                posix_kill(posix_getpid(), SIGKILL); // skip PHPUnit/Laravel shutdown in the child
            }
            $pids[] = $pid;
        }
        usleep(300000);
        touch($dir.'/go');
        foreach ($pids as $pid) {
            pcntl_waitpid($pid, $status);
        }
        DB::reconnect();

        $codes = [];
        for ($i = 0; $i < self::PROCESSES; $i++) {
            $codes[] = (int) @file_get_contents($dir.'/result-'.$i);
        }
        $calls = is_file($dir.'/calls') ? count(file($dir.'/calls', FILE_IGNORE_NEW_LINES)) : 0;
        array_map('unlink', glob($dir.'/*') ?: []);
        rmdir($dir);

        return ['codes' => $codes, 'calls' => $calls];
    }
}
