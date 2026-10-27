<?php

namespace Tests\Unit;

use App\Services\ProductStudio\LocalProductDraftTemplate;
use PHPUnit\Framework\TestCase;

final class LocalProductDraftTemplateTest extends TestCase
{
    public function test_explicit_name_is_not_contaminated_by_following_product_description(): void
    {
        $draft = (new LocalProductDraftTemplate)->fromBrief(
            'KMJ Calibration Studio is proposed projector calibration software with camera-assisted alignment.'
        );

        self::assertSame('KMJ Calibration Studio', $draft['name']);
        self::assertSame('other', $draft['category']);
        self::assertSame('product', $draft['offering_type']);
        self::assertStringContainsString('camera-assisted alignment', $draft['description']);
        self::assertStringContainsString('not independently verified', $draft['description']);
        self::assertStringContainsString('Not yet generated', $draft['photo_prompt']);
    }

    public function test_explicit_service_name_preserves_review_only_status(): void
    {
        $draft = (new LocalProductDraftTemplate)->fromBrief(
            'KMJ Projector Support is an installation service for proposed cinema systems.'
        );

        self::assertSame('KMJ Projector Support', $draft['name']);
        self::assertSame('service', $draft['offering_type']);
        self::assertStringContainsString('installation service', $draft['description']);
        self::assertStringContainsString('not AI-generated copy', $draft['description']);
    }

    public function test_brief_without_explicit_identity_keeps_existing_typo_correction(): void
    {
        $draft = (new LocalProductDraftTemplate)->fromBrief('inteactive wall projetion SOFTWARE');

        self::assertSame('Interactive wall Projection SOFTWARE', $draft['name']);
        self::assertSame('other', $draft['category']);
    }
}
