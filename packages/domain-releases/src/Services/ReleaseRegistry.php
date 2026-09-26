<?php

namespace KMJ\MainPlatform\Releases\Services;

use DomainException;
use Illuminate\Support\Facades\DB;
use InvalidArgumentException;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Releases\Models\ProductRelease;
use KMJ\MainPlatform\Releases\Models\ReleaseArtifact;

final class ReleaseRegistry
{
    public function stage(
        string $productId,
        string $version,
        string $artifactDigest,
        string $provenanceRef,
        string $filename,
        string $disk,
        string $path,
        ?string $mediaType = null,
        ?int $sizeBytes = null,
    ): ProductRelease {
        [$version, $artifactDigest, $provenanceRef, $filename, $disk, $path] =
            $this->validateStageInput(
                $version,
                $artifactDigest,
                $provenanceRef,
                $filename,
                $disk,
                $path,
                $sizeBytes,
            );

        Product::query()->findOrFail($productId);

        return DB::transaction(function () use (
            $productId,
            $version,
            $artifactDigest,
            $provenanceRef,
            $filename,
            $disk,
            $path,
            $mediaType,
            $sizeBytes,
        ): ProductRelease {
            $release = ProductRelease::query()->firstOrCreate(
                ['product_id' => $productId, 'version' => $version],
                [
                    'artifact_digest' => $artifactDigest,
                    'provenance_ref' => $provenanceRef,
                    'status' => 'staged',
                ],
            );

            $this->assertReleaseFacts(
                $release,
                $artifactDigest,
                $provenanceRef,
            );

            $artifact = ReleaseArtifact::query()->firstOrCreate(
                ['release_id' => $release->getKey()],
                [
                    'filename' => $filename,
                    'disk' => $disk,
                    'path' => $path,
                    'media_type' => $mediaType,
                    'size_bytes' => $sizeBytes,
                    'digest' => $artifactDigest,
                ],
            );

            $this->assertArtifactFacts(
                $artifact,
                $filename,
                $disk,
                $path,
                $artifactDigest,
            );

            return $release->fresh('artifact') ?? $release;
        });
    }

    public function promote(string $releaseId): ProductRelease
    {
        return DB::transaction(function () use ($releaseId): ProductRelease {
            $release = ProductRelease::query()
                ->with('artifact')
                ->lockForUpdate()
                ->findOrFail($releaseId);

            if ($release->status === 'promoted') {
                return $release;
            }

            if ($release->status === 'revoked') {
                throw new DomainException('A revoked release cannot be promoted.');
            }

            if (! in_array($release->status, ['staged', 'signed'], true)) {
                throw new DomainException('Only staged or signed releases can be promoted.');
            }

            if (! $release->artifact instanceof ReleaseArtifact) {
                throw new DomainException('A release artifact is required before promotion.');
            }

            $release->forceFill([
                'status' => 'promoted',
                'promoted_at' => now(),
                'revoked_at' => null,
            ])->save();

            return $release->fresh('artifact') ?? $release;
        });
    }

    public function revoke(string $releaseId): ProductRelease
    {
        return DB::transaction(function () use ($releaseId): ProductRelease {
            $release = ProductRelease::query()
                ->lockForUpdate()
                ->findOrFail($releaseId);

            if ($release->status !== 'revoked') {
                $release->forceFill([
                    'status' => 'revoked',
                    'revoked_at' => now(),
                ])->save();
            }

            return $release->fresh('artifact') ?? $release;
        });
    }

    private function validateStageInput(
        string $version,
        string $artifactDigest,
        string $provenanceRef,
        string $filename,
        string $disk,
        string $path,
        ?int $sizeBytes,
    ): array {
        $version = trim($version);
        $artifactDigest = trim($artifactDigest);
        $provenanceRef = trim($provenanceRef);
        $filename = trim($filename);
        $disk = trim($disk);
        $path = ltrim(trim($path), '/');

        if (
            $version === ''
            || strlen($version) > 96
            || $provenanceRef === ''
            || $filename === ''
            || $disk === ''
            || $path === ''
        ) {
            throw new InvalidArgumentException('Release metadata is incomplete.');
        }

        if (! preg_match('/^sha256:[a-f0-9]{64}$/', $artifactDigest)) {
            throw new InvalidArgumentException('Artifact digest must be a lowercase sha256 digest.');
        }

        if (preg_match('#(^|/)\.\.(/|$)#', $path)) {
            throw new InvalidArgumentException('Artifact path traversal is not allowed.');
        }

        if ($sizeBytes !== null && $sizeBytes < 0) {
            throw new InvalidArgumentException('Artifact size cannot be negative.');
        }

        return [$version, $artifactDigest, $provenanceRef, $filename, $disk, $path];
    }

    private function assertReleaseFacts(
        ProductRelease $release,
        string $artifactDigest,
        string $provenanceRef,
    ): void {
        if (
            $release->artifact_digest !== $artifactDigest
            || $release->provenance_ref !== $provenanceRef
        ) {
            throw new DomainException('Release version is already bound to different provenance.');
        }
    }

    private function assertArtifactFacts(
        ReleaseArtifact $artifact,
        string $filename,
        string $disk,
        string $path,
        string $digest,
    ): void {
        if (
            $artifact->filename !== $filename
            || $artifact->disk !== $disk
            || $artifact->path !== $path
            || $artifact->digest !== $digest
        ) {
            throw new DomainException('Release artifact is already bound to different storage facts.');
        }
    }
}
