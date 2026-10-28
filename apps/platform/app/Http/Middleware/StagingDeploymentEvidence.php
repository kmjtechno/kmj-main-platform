<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

final class StagingDeploymentEvidence
{
    public function handle(Request $request, Closure $next): Response
    {
        $response = $next($request);

        if ($request->getHost() !== 'staging.kmjtechno.com') {
            return $response;
        }

        $sha = $this->currentRepositorySha();
        if ($sha !== null) {
            $response->headers->set('X-KMJ-Deploy-SHA', $sha);
            $response->headers->set('Cache-Control', 'no-store');
        }

        return $response;
    }

    /**
     * @param  array<int|string, int>  $stat
     */
    private static function parseRootAttestation(string $data, array $stat): ?string
    {
        if ((int) ($stat['uid'] ?? -1) !== 0
            || (int) ($stat['nlink'] ?? -1) !== 1
            || ((int) ($stat['mode'] ?? 0) & 0022) !== 0
            || (int) ($stat['size'] ?? 0) < 40
            || (int) ($stat['size'] ?? 0) > 41) {
            return null;
        }

        return preg_match('/\\A[0-9a-f]{40}\\n?\\z/', $data) === 1
            ? trim($data)
            : null;
    }

    private function currentRepositorySha(): ?string
    {
        // Production/customer origins never expose this header. For staging,
        // a root-owned immutable release attestation is the preferred source.
        // Reading a git HEAD as www-data requires opening repository metadata
        // to the web-server account and fails with restricted candidate builds.
        $attestation = base_path('public/build/.kmj-deploy-sha');

        if (is_file($attestation) || is_link($attestation)) {
            if (is_link($attestation) || ! is_file($attestation) || ! is_readable($attestation)) {
                return null;
            }

            $stat = @stat($attestation);
            $data = @file_get_contents($attestation);

            return is_array($stat) && is_string($data)
                ? self::parseRootAttestation($data, $stat)
                : null;
        }

        // Only local/uninstalled staging fall back to legacy .git detection;
        // no privileged file permissions are modified to support fallback.
        $gitPath = dirname(base_path(), 2).'/.git';
        $gitDir = $gitPath;

        if (is_file($gitPath)) {
            $pointer = trim((string) @file_get_contents($gitPath));
            if (! str_starts_with($pointer, 'gitdir: ')) {
                return null;
            }

            $candidate = trim(substr($pointer, strlen('gitdir: ')));
            $gitDir = str_starts_with($candidate, '/')
                ? $candidate
                : dirname($gitPath).'/'.$candidate;
        }

        if (! is_dir($gitDir)) {
            return null;
        }

        $head = trim((string) @file_get_contents($gitDir.'/HEAD'));
        if (preg_match('/^[0-9a-f]{40}$/', $head) === 1) {
            return $head;
        }

        if (! str_starts_with($head, 'ref: ')) {
            return null;
        }

        $ref = trim(substr($head, strlen('ref: ')));
        if (preg_match('#^refs/[A-Za-z0-9._/-]+$#', $ref) !== 1 || str_contains($ref, '..')) {
            return null;
        }

        // Worktrees store HEAD under a private gitdir and branch refs in a
        // shared Git common directory. Read both, without executing git.
        $refDirs = [$gitDir];
        $common = trim((string) @file_get_contents($gitDir.'/commondir'));
        if ($common !== '') {
            $commonDir = str_starts_with($common, '/')
                ? $common
                : $gitDir.'/'.$common;
            if (is_dir($commonDir)) {
                $refDirs[] = $commonDir;
            }
        }

        foreach ($refDirs as $refDir) {
            $loose = trim((string) @file_get_contents($refDir.'/'.$ref));
            if (preg_match('/^[0-9a-f]{40}$/', $loose) === 1) {
                return $loose;
            }

            $packed = @file($refDir.'/packed-refs', FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
            if (! is_array($packed)) {
                continue;
            }

            foreach ($packed as $line) {
                if ($line === '' || str_starts_with($line, '#') || str_starts_with($line, '^')) {
                    continue;
                }

                $parts = preg_split('/\\s+/', trim($line), 2);
                if (! is_array($parts)) {
                    continue;
                }

                [$sha, $name] = array_pad($parts, 2, null);
                if ($name === $ref && is_string($sha) && preg_match('/^[0-9a-f]{40}$/', $sha) === 1) {
                    return $sha;
                }
            }
        }

        return null;
    }
}
