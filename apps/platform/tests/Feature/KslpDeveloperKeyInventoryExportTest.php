<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\Licensing\Kslp\KslpDeveloperKeys;
use App\Services\Licensing\Kslp\KslpInventoryCsv;
use App\Services\Licensing\Kslp\KslpIssuerSubscriptionAuthority;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

final class KslpDeveloperKeyInventoryExportTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
        config()->set('services.kmj_developer_licensing.enabled', true);
    }

    /** @return array{User, string} */
    private function owner(string $name): array
    {
        $owner = User::factory()->create();
        $this->actingAs($owner)->post('/organizations', ['name' => $name]);
        $orgId = (string) DB::table('organization_memberships')
            ->where('user_id', $owner->id)
            ->value('organization_id');

        return [$owner, $orgId];
    }

    private function key(string $org, string $code, string $name, string $customer, int $ownerId): array
    {
        app(KslpIssuerSubscriptionAuthority::class)->subscribe($org, 'professional', 5, 50);
        app(KslpIssuerSubscriptionAuthority::class)->registerProduct($org, $code, $name);

        return app(KslpDeveloperKeys::class)
            ->issue($org, $code, $customer, 'trial', (string) $ownerId);
    }

    public function test_masked_csv_is_scoped_to_one_authorized_issuer_with_no_plaintext_key_or_customer_data(): void
    {
        [$ownerA, $orgA] = $this->owner('Export Owner A');
        $keyA = $this->key($orgA, 'VENDOR.EXPORTA', '=2+3', 'secret-customer-A', $ownerA->id);
        [$ownerB, $orgB] = $this->owner('Export Owner B');
        $keyB = $this->key($orgB, 'VENDOR.EXPORTB', 'Other Organization App', 'secret-customer-B', $ownerB->id);

        config()->set('services.kmj_developer_licensing.enabled', false);
        $response = $this->actingAs($ownerA)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/developer/keys/export?organization_id='.$orgA);

        $response->assertOk()
            ->assertHeader('Cache-Control', 'private, no-store, max-age=0')
            ->assertHeader('X-Content-Type-Options', 'nosniff');
        $csv = $response->streamedContent();

        self::assertStringContainsString('product_code,application_name,license_id,masked_key_prefix', $csv);
        self::assertStringContainsString('VENDOR.EXPORTA', $csv);
        self::assertStringContainsString("'=2+3", $csv);
        self::assertStringContainsString((string) $keyA['license_id'], $csv);
        self::assertStringContainsString(substr($keyA['key'], 0, 12), $csv);

        self::assertStringNotContainsString($keyA['key'], $csv);
        self::assertStringNotContainsString(hash('sha256', $keyA['key']), $csv);
        self::assertStringNotContainsString('secret-customer-A', $csv);
        self::assertStringNotContainsString('secret-customer-B', $csv);
        self::assertStringNotContainsString((string) $keyB['license_id'], $csv);
        self::assertStringNotContainsString('VENDOR.EXPORTB', $csv);
        self::assertSame(1000, KslpInventoryCsv::MAX_ROWS);
    }

    public function test_cross_tenant_csv_export_and_unconfirmed_password_are_denied(): void
    {
        [$owner, $org] = $this->owner('Protected Export Owner');
        $this->key($org, 'VENDOR.PRIVATEEXPORT', 'Protected App', 'secret-customer', $owner->id);
        $attacker = User::factory()->create();

        $this->actingAs($attacker)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/developer/keys/export?organization_id='.$org)
            ->assertForbidden();

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => 0])
            ->get('/developer/keys/export?organization_id='.$org)
            ->assertRedirect();

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->get('/developer/keys/export?organization_id=not-a-uuid')
            ->assertSessionHasErrors('organization_id');
    }

    public function test_csv_cells_neutralize_spreadsheet_formula_inputs_and_control_characters(): void
    {
        self::assertSame("'=SUM(1,2)", KslpInventoryCsv::safeCell('=SUM(1,2)'));
        self::assertSame("'  +CMD", KslpInventoryCsv::safeCell('  +CMD'));
        self::assertSame("' @HYPERLINK", KslpInventoryCsv::safeCell("\t@HYPERLINK"));
        self::assertSame('safe text', KslpInventoryCsv::safeCell("safe\ntext"));
        self::assertSame('', KslpInventoryCsv::safeCell(null));
    }
}
