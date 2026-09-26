<?php

namespace App\Services\Releases;

use DomainException;
use Illuminate\Filesystem\FilesystemAdapter;
use Illuminate\Support\Facades\Storage;
use KMJ\MainPlatform\Releases\Models\ProductRelease;
use KMJ\MainPlatform\Releases\Models\ReleaseArtifact;
use RuntimeException;
use Symfony\Component\HttpFoundation\StreamedResponse;

final class ReleaseArtifactDelivery
{
    public function download(ProductRelease $release): StreamedResponse
    {
        $artifact = $release->artifact;

        if (! $artifact instanceof ReleaseArtifact) {
            throw new DomainException('Release artifact is missing.');
        }

        $filesystem = Storage::disk($artifact->disk);

        if (! $filesystem->exists($artifact->path)) {
            throw new RuntimeException('Release artifact is not available.');
        }

        $this->verifyDigest($filesystem, $artifact);

        $headers = [
            'Cache-Control' => 'private, no-store',
            'X-KMJ-Artifact-SHA256' => $artifact->digest,
        ];

        if (is_string($artifact->media_type) && $artifact->media_type !== '') {
            $headers['Content-Type'] = $artifact->media_type;
        }

        return $filesystem->download(
            $artifact->path,
            $artifact->filename,
            $headers,
        );
    }

    private function verifyDigest(
        FilesystemAdapter $filesystem,
        ReleaseArtifact $artifact,
    ): void {
        $stream = $filesystem->readStream($artifact->path);

        if (! is_resource($stream)) {
            throw new RuntimeException('Release artifact cannot be read.');
        }

        $context = hash_init('sha256');

        try {
            hash_update_stream($context, $stream);
        } finally {
            fclose($stream);
        }

        $actual = 'sha256:'.hash_final($context);

        if (! hash_equals($artifact->digest, $actual)) {
            throw new DomainException('Release artifact digest verification failed.');
        }
    }
}
