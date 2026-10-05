<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Str;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('codebridge_device_project_grants', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->foreignUuid('credential_id')->constrained('codebridge_device_credentials')->cascadeOnDelete();
            $table->string('tenant_id', 64);
            $table->string('device_id', 64);
            $table->string('project_id', 64);
            $table->string('project_name', 128);
            $table->string('repository', 255)->nullable();
            $table->json('permissions');
            $table->string('gate_preset', 32)->default('standard');
            $table->string('status', 24)->default('authorized');
            $table->timestamp('revoked_at')->nullable();
            $table->timestamps();

            $table->unique(['tenant_id', 'device_id', 'project_id'], 'codebridge_project_grant_unique');
            $table->index(['credential_id', 'status']);
            $table->index(['tenant_id', 'device_id', 'revoked_at'], 'codebridge_project_grant_device_idx');
        });

        $pairings = DB::table('codebridge_device_pairings')
            ->whereIn('status', ['approved', 'consumed'])
            ->whereNotNull('activation_id')
            ->whereNotNull('tenant_id')
            ->orderBy('created_at')
            ->get();

        foreach ($pairings as $pairing) {
            $credential = DB::table('codebridge_device_credentials')
                ->where('activation_id', $pairing->activation_id)
                ->first();

            if (! $credential) {
                continue;
            }

            $permissions = [];
            if (is_string($pairing->requested_permissions) && $pairing->requested_permissions !== '') {
                try {
                    $decoded = json_decode($pairing->requested_permissions, true, 8, JSON_THROW_ON_ERROR);
                    $permissions = array_values(array_unique(array_values(array_intersect(
                        ['read', 'write', 'execute'],
                        array_filter(is_array($decoded) ? $decoded : [], 'is_string'),
                    ))));
                } catch (Throwable) {
                    $permissions = [];
                }
            }

            if ($permissions === []) {
                continue;
            }

            DB::table('codebridge_device_project_grants')->updateOrInsert(
                [
                    'tenant_id' => $pairing->tenant_id,
                    'device_id' => $pairing->device_id,
                    'project_id' => $pairing->project_id,
                ],
                [
                    'id' => (string) Str::uuid(),
                    'credential_id' => $credential->id,
                    'project_name' => $pairing->project_name,
                    'repository' => null,
                    'permissions' => json_encode($permissions, JSON_THROW_ON_ERROR),
                    'gate_preset' => 'standard',
                    'status' => 'authorized',
                    'revoked_at' => null,
                    'created_at' => $pairing->created_at ?? now(),
                    'updated_at' => now(),
                ],
            );
        }
    }

    public function down(): void
    {
        Schema::dropIfExists('codebridge_device_project_grants');
    }
};
