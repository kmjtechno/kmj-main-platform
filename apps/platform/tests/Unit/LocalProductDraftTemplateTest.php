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

    public function test_colon_separates_product_name_from_proposed_description(): void
    {
        $draft = (new LocalProductDraftTemplate)->fromBrief(
            'KMJ CineCore: proposed stereoscopic projection software for dual projectors.'
        );

        self::assertSame('KMJ CineCore', $draft['name']);
        self::assertStringContainsString('stereoscopic projection software', $draft['description']);
        self::assertStringContainsString('Not yet generated', $draft['banner_prompt']);
    }

    public function test_em_dash_separates_service_name_without_inventing_capabilities(): void
    {
        $draft = (new LocalProductDraftTemplate)->fromBrief(
            'KMJ Cinema Support — proposed installation service for venue operators.'
        );

        self::assertSame('KMJ Cinema Support', $draft['name']);
        self::assertSame('service', $draft['offering_type']);
        self::assertStringContainsString('not independently verified', $draft['description']);
    }

    public function test_explicit_single_word_product_name_is_not_contaminated(): void
    {
        $draft = (new LocalProductDraftTemplate)->fromBrief(
            'CineCore: proposed stereo playback'
        );

        self::assertSame('CineCore', $draft['name']);
        self::assertStringContainsString('proposed stereo playback', $draft['description']);
    }

    public function test_generic_colon_heading_is_not_treated_as_product_identity(): void
    {
        $draft = (new LocalProductDraftTemplate)->fromBrief(
            'Software: proposed stereo playback'
        );

        self::assertSame('proposed stereo playback', $draft['name']);
        self::assertStringContainsString('not independently verified', $draft['description']);
    }

    public function test_brief_without_explicit_identity_keeps_existing_typo_correction(): void
    {
        $draft = (new LocalProductDraftTemplate)->fromBrief('inteactive wall projetion SOFTWARE');

        self::assertSame('Interactive wall Projection SOFTWARE', $draft['name']);
        self::assertSame('other', $draft['category']);
    }

    public function test_product_name_label_uses_its_value_not_label(): void
    {
        $draft = (new LocalProductDraftTemplate)->fromBrief(
            'Product name: KMJ CineCore — proposed dual projector stereo playback software.'
        );

        self::assertSame('KMJ CineCore', $draft['name']);
        self::assertStringContainsString('dual projector stereo playback', $draft['description']);
    }

    public function test_single_word_name_field_preserves_identity(): void
    {
        $draft = (new LocalProductDraftTemplate)->fromBrief(
            'Name: CineCore. Proposed cinema playback technology.'
        );

        self::assertSame('CineCore', $draft['name']);
        self::assertStringContainsString('Proposed cinema', $draft['description']);
    }

    public function test_generic_product_heading_is_not_used_as_name(): void
    {
        $draft = (new LocalProductDraftTemplate)->fromBrief(
            'Product: KMJ Cinema Suite — proposed stereo playback workflow.'
        );

        self::assertSame('KMJ Cinema Suite', $draft['name']);
    }

    public function test_labeled_versioned_name_keeps_decimal_without_description_pollution(): void
    {
        $draft = (new LocalProductDraftTemplate)->fromBrief(
            'Product name: KMJ CineCore 2.1 — proposed stereo playback software.'
        );

        self::assertSame('KMJ CineCore 2.1', $draft['name']);
        self::assertStringContainsString('proposed stereo playback', $draft['description']);
    }

    public function test_versioned_name_field_stops_at_following_sentence(): void
    {
        $draft = (new LocalProductDraftTemplate)->fromBrief(
            'Name: CineCore v2.0. Proposed cinema playback technology.'
        );

        self::assertSame('CineCore v2.0', $draft['name']);
        self::assertStringContainsString('Proposed cinema', $draft['description']);
    }

    public function test_unlabeled_versioned_name_before_colon_is_preserved(): void
    {
        $draft = (new LocalProductDraftTemplate)->fromBrief(
            'KMJ CineCore 2.0: proposed stereo playback.'
        );

        self::assertSame('KMJ CineCore 2.0', $draft['name']);
    }

}
