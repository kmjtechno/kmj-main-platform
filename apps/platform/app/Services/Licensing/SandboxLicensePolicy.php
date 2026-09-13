<?php

namespace App\Services\Licensing;

final class SandboxLicensePolicy
{
    public const MAX_LIFETIME_SECONDS = 30 * 60;

    public const MAX_FUTURE_ISSUED_AT_SKEW_SECONDS = 60;

    private function __construct() {}
}
