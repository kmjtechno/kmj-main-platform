<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\TestCase;

final class CodeBridgeAdminHttpTest extends TestCase
{
    use RefreshDatabase;

    public function test_guest_and_regular_user_cannot_manage_codebridge_credentials(): void
    {
        $this->postJson('/operator/codebridge/devices/enroll', [])->assertUnauthorized();

        $user = User::factory()->create(['email_verified_at' => now()]);
        $this->actingAs($user)->withSession(['auth.password_confirmed_at' => time()])
            ->postJson('/operator/codebridge/devices/enroll', $this->validPayload())
            ->assertForbidden();
    }

    public function test_owner_requests_are_strictly_validated_before_mutation(): void
    {
        $owner = $this->platformOwner();
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->postJson('/operator/codebridge/devices/enroll', ['license_id' => 'not-a-uuid', 'activation_id' => 'x', 'tenant_id' => '../tenant', 'device_id' => ''])
            ->assertUnprocessable()
            ->assertJsonValidationErrors(['license_id', 'activation_id', 'tenant_id', 'device_id']);

        self::assertSame(0, DB::table('codebridge_device_credentials')->count());
    }

    public function test_cross_tenant_license_binding_fails_closed(): void
    {
        [$license, $activation] = $this->fixture('tenant-a');
        $owner = $this->platformOwner();

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->postJson('/operator/codebridge/devices/enroll', ['license_id'=>$license,'activation_id'=>$activation,'tenant_id'=>'tenant-b','device_id'=>'device-a'])
            ->assertNotFound();

        self::assertSame(0, DB::table('codebridge_device_credentials')->count());
    }

    public function test_owner_can_enroll_rotate_and_revoke_with_no_store_responses(): void
    {
        [$license, $activation] = $this->fixture('tenant-a');
        $owner = $this->platformOwner();
        $session=['auth.password_confirmed_at'=>time()];
        $payload=['license_id'=>$license,'activation_id'=>$activation,'tenant_id'=>'tenant-a','device_id'=>'device-a'];

        $enroll=$this->actingAs($owner)->withSession($session)->postJson('/operator/codebridge/devices/enroll',$payload)
            ->assertCreated()->assertHeader('Cache-Control','no-store');
        $old=$enroll->json('credential');
        self::assertIsString($old);

        $manage=['license_id'=>$license,'tenant_id'=>'tenant-a','device_id'=>'device-a'];
        $rotate=$this->actingAs($owner)->withSession($session)->postJson('/operator/codebridge/devices/rotate',$manage)
            ->assertOk()->assertHeader('Cache-Control','no-store');
        self::assertNotSame($old,$rotate->json('credential'));

        $this->actingAs($owner)->withSession($session)->postJson('/operator/codebridge/devices/revoke',$manage)
            ->assertOk()->assertHeader('Cache-Control','no-store')->assertJson(['revoked'=>true]);
        self::assertNotNull(DB::table('codebridge_device_credentials')->where('license_id',$license)->value('revoked_at'));
    }

    /** @return array{string,string} */
    private function fixture(string $tenant): array
    {
        $license=(string) Str::uuid(); $activation=(string) Str::uuid(); $now=now();
        DB::table('kslp_licenses')->insert(['id'=>$license,'customer_id'=>$tenant,'product'=>'KMJ_CODEBRIDGE','plan'=>'professional','status'=>'active','sequence'=>1,'starts_at'=>$now->copy()->subMinute(),'expires_at'=>$now->copy()->addYear(),'grace_until'=>$now->copy()->addYear()->addDays(2),'created_at'=>$now,'updated_at'=>$now]);
        DB::table('kslp_activations')->insert(['id'=>$activation,'license_id'=>$license,'server_identity'=>'ed25519:http-test','machine_identity_hash'=>str_repeat('a',64),'idempotency_key'=>'http-'.Str::uuid(),'activated_at'=>$now,'created_at'=>$now,'updated_at'=>$now]);
        $product=(string) Str::uuid();
        DB::table('products')->insert(['id'=>$product,'slug'=>'codebridge','name'=>'CodeBridge','status'=>'active','lifecycle'=>'available','is_public'=>false,'sort_order'=>100,'purchase_enabled'=>false,'licensing_enabled'=>true,'created_at'=>$now,'updated_at'=>$now]);
        DB::table('plans')->insert(['id'=>(string) Str::uuid(),'product_id'=>$product,'code'=>'codebridge.professional','name'=>'CodeBridge Professional','pricing_model'=>'license','status'=>'active','trial_days'=>0,'features'=>json_encode(['read'=>true]),'limits'=>json_encode(['devices'=>2]),'created_at'=>$now,'updated_at'=>$now]);
        return [$license,$activation];
    }

    /** @return array<string,string> */
    private function validPayload(): array
    {
        return ['license_id'=>(string) Str::uuid(),'activation_id'=>(string) Str::uuid(),'tenant_id'=>'tenant-a','device_id'=>'device-a'];
    }

    private function platformOwner(): User
    {
        $user=User::factory()->create(['email_verified_at'=>now(),'is_platform_owner'=>true,'platform_owner_granted_at'=>now()]);
        DB::table('passkeys')->insert(['user_id'=>$user->id,'name'=>'CodeBridge admin passkey','credential_id'=>'codebridge-admin-'.Str::uuid(),'credential'=>'{}','created_at'=>now(),'updated_at'=>now()]);
        return $user;
    }
}
