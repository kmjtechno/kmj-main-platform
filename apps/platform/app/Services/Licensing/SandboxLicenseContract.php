<?php

namespace App\Services\Licensing;

final class SandboxLicenseContract
{
    public const CURRENT_VERSION = 'kmj.sandbox.v1';

    public static function supports(mixed $version): bool
    {
        return is_string($version) && hash_equals(self::CURRENT_VERSION, $version);
    }
}
