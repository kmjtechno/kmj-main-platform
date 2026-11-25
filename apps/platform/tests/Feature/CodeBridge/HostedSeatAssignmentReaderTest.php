<?php

declare(strict_types=1);

namespace Tests\Feature\CodeBridge;

use App\Models\User;
use App\Services\CodeBridge\HostedSeatAssignmentReader;
use App\Services\CodeBridge\HostedSeatAuthorization;
use App\Services\Licensing\Kslp\KslpCodec;
use App\Services\Licensing\Kslp\KslpKeyRegistry;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class HostedSeatAssignmentReaderTest extends TestCase
{
    use RefreshDatabase;

    public function test_only_current_explicit_assignment_is_readable(): void
    {
        $owner = User::factory()->create(['email_verified_at' => now()]);
        $member = User::factory()->create(['email_verified_at' => now()]);
        $foreign = User::factory()->create(['email_verified_at' => now()]);
        $org = (string) app(OrganizationCreator::class)->create('Team seat test', (int) $owner->getKey())->getKey();
        $membership = (string) Str::uuid();
        $license = (string) Str::uuid();
        $seat = (string) Str::uuid();
        DB::table('organization_memberships')->insert([
            'id' => $membership, 'organization_id' => $org, 'user_id' => $member->getKey(),
            'role' => 'member', 'created_at' => now(), 'updated_at' => now(),
        ]);
        DB::table('kslp_licenses')->insert([
            'id' => $license, 'customer_id' => $org, 'product' => 'KMJ_CODEBRIDGE', 'plan' => 'team',
            'status' => 'active', 'sequence' => 1, 'starts_at' => now()->subDay(), 'expires_at' => now()->addDay(),
            'created_at' => now(), 'updated_at' => now(),
        ]);
        $reader = app(HostedSeatAssignmentReader::class);
        self::assertNull($reader->forMember($member, $org, $seat));

        DB::table('codebridge_hosted_seat_assignments')->insert([
            'id' => $seat, 'organization_id' => $org, 'membership_id' => $membership, 'license_id' => $license,
            'assignment_revision' => 1, 'starts_at' => now()->subHour(), 'ends_at' => now()->addHour(),
            'created_at' => now(), 'updated_at' => now(),
        ]);

        self::assertSame([
            'organization_id' => $org, 'membership_id' => $membership, 'user_id' => (string) $member->getKey(),
            'license_id' => $license, 'seat_id' => $seat, 'assignment_revision' => 1,
        ], $reader->forMember($member, $org, $seat));
        self::assertNull($reader->forMember($owner, $org, $seat));
        self::assertNull($reader->forMember($foreign, $org, $seat));
        self::assertNull($reader->forMember($member, (string) Str::uuid(), $seat));

        $assignment = $reader->forMember($member, $org, $seat);
        self::assertNotNull($assignment);
        $pair = sodium_crypto_sign_keypair();
        $encoded = rtrim(strtr(base64_encode(sodium_crypto_sign_publickey($pair)), '+/', '-_'), '=');
        $registry = app(KslpKeyRegistry::class);
        $registry->publish('seat-key', 'license', $encoded, 'active', 'KMJ_CODEBRIDGE', now()->addHour());
        $registry->publish('other-product', 'license', $encoded, 'active', 'KMJ_OMNIDESK', now()->addHour());
        $registry->publish('generic-key', 'license', $encoded);
        $now = now()->getTimestamp();
        $claims = [
            ...$assignment,
            'protocol_version' => 'KSLP-seat-v1',
            'aud' => 'kmj-codebridge-hosted-seat',
            'product' => 'KMJ_CODEBRIDGE',
            'plan' => 'team',
            'iat' => $now,
            'nbf' => $now,
            'exp' => $now + 300,
        ];
        $sign = static fn (string $message): string => sodium_crypto_sign_detached($message, sodium_crypto_sign_secretkey($pair));
        $proof = KslpCodec::encode($claims, 'seat-key', $sign);
        $authorization = app(HostedSeatAuthorization::class);
        self::assertSame('seat:'.$seat, $authorization->subjectForMember($member, $org, $seat, $proof, 'seat-key'));
        self::assertNull($authorization->subjectForMember($owner, $org, $seat, $proof, 'seat-key'));
        self::assertNull($authorization->subjectForMember($foreign, $org, $seat, $proof, 'seat-key'));
        self::assertNull($authorization->subjectForMember($member, $org, $seat, KslpCodec::encode($claims, 'other-product', $sign), 'other-product'));
        self::assertNull($authorization->subjectForMember($member, $org, $seat, KslpCodec::encode($claims, 'generic-key', $sign), 'generic-key'));
        $registry->revoke('seat-key');
        self::assertNull($authorization->subjectForMember($member, $org, $seat, $proof, 'seat-key'));


        DB::table('codebridge_hosted_seat_assignments')->where('id', $seat)->update(['assignment_revision' => 2]);
        self::assertSame(2, $reader->forMember($member, $org, $seat)['assignment_revision']);
        DB::table('kslp_licenses')->where('id', $license)->update(['plan' => 'pro']);
        self::assertNull($reader->forMember($member, $org, $seat));
        DB::table('kslp_licenses')->where('id', $license)->update(['plan' => 'team', 'revoked_at' => now()]);
        self::assertNull($reader->forMember($member, $org, $seat));
        DB::table('kslp_licenses')->where('id', $license)->update(['revoked_at' => null]);
        DB::table('codebridge_hosted_seat_assignments')->where('id', $seat)->update(['ends_at' => now()->subMinute()]);
        self::assertNull($reader->forMember($member, $org, $seat));
        DB::table('codebridge_hosted_seat_assignments')->where('id', $seat)->update(['ends_at' => now()->addHour(), 'revoked_at' => now()]);
        self::assertNull($reader->forMember($member, $org, $seat));
        $this->assertDatabaseCount('codebridge_usage_executions', 0);
    }
}
