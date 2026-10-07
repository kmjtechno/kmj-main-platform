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

    private function currentRepositorySha(): ?string
    {
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

        $loose = trim((string) @file_get_contents($gitDir.'/'.$ref));
        if (preg_match('/^[0-9a-f]{40}$/', $loose) === 1) {
            return $loose;
        }

        $packed = @file($gitDir.'/packed-refs', FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
        if (! is_array($packed)) {
            return null;
        }

        foreach ($packed as $line) {
            if ($line === '' || str_starts_with($line, '#') || str_starts_with($line, '^')) {
                continue;
            }

            $parts = preg_split('/\s+/', trim($line), 2);
            if (! is_array($parts)) {
                continue;
            }

            [$sha, $name] = array_pad($parts, 2, null);
            if ($name === $ref && is_string($sha) && preg_match('/^[0-9a-f]{40}$/', $sha) === 1) {
                return $sha;
            }
        }

        return null;
    }
}
