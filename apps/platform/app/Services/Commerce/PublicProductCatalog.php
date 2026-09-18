<?php

namespace App\Services\Commerce;

final class PublicProductCatalog
{
    /**
     * @return array<int, array<string, mixed>>
     */
    public function all(): array
    {
        return [$this->calibration()];
    }

    /**
     * @return array<string, mixed>|null
     */
    public function find(string $slug): ?array
    {
        return $slug === 'kmj-calibration-pro' ? $this->calibration() : null;
    }

    /**
     * Evidence-backed public projection for the current Calibration repository state.
     *
     * @return array<string, mixed>
     */
    private function calibration(): array
    {
        return [
            'slug' => 'kmj-calibration-pro',
            'name' => 'KMJ Calibration Pro',
            'lifecycle' => 'development-preview',
            'lifecycle_label' => 'Development preview',
            'purchase_enabled' => false,
            'eyebrow' => 'Projector + camera calibration',
            'headline' => 'See the complete calibration workflow before touching hardware.',
            'summary' => 'A guided projector-camera calibration experience being built around a native C++ foundation, deterministic verification and fail-closed runtime behavior.',
            'truth' => [
                'physical_capability_certified' => false,
                'status' => 'Buildable C++ foundation; physical calibration capability is not yet certified.',
            ],
            'proof' => [
                [
                    'title' => 'Native C++ foundation',
                    'detail' => 'C++23, CMake and Ninja foundation with Debug and Release verification.',
                    'state' => 'repository-verified',
                ],
                [
                    'title' => 'Fail-closed behavior',
                    'detail' => 'Calibration, warp and storage placeholders refuse to claim success until implemented.',
                    'state' => 'repository-verified',
                ],
                [
                    'title' => 'Guided product experience',
                    'detail' => 'The public demo explains the intended Setup → Capture → Analyze → Results flow without claiming physical output.',
                    'state' => 'simulation',
                ],
            ],
            'demo' => [
                'kind' => 'calibration',
                'simulation' => true,
                'label' => 'Interactive workflow simulation',
                'steps' => [
                    ['key' => 'setup', 'label' => 'Setup', 'detail' => 'Choose projector and camera roles.'],
                    ['key' => 'capture', 'label' => 'Capture', 'detail' => 'Preview structured-light capture sequencing.'],
                    ['key' => 'analyze', 'label' => 'Analyze', 'detail' => 'See how correspondence and geometry checks fit together.'],
                    ['key' => 'results', 'label' => 'Results', 'detail' => 'Review a synthetic result state with clear non-certified labeling.'],
                ],
            ],
            'cta' => [
                'primary' => 'Launch virtual demo',
                'secondary' => 'Development preview',
            ],
        ];
    }
}
