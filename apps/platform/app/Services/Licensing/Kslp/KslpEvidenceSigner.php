<?php

namespace App\Services\Licensing\Kslp;

interface KslpEvidenceSigner
{
    public function keyId(): string;

    public function sign(string $canonicalManifest): string;
}
