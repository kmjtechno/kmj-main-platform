<?php

namespace App\Services\Licensing;

final readonly class ProductLicenseProfile
{
    /**
     * @param  list<string>  $allowedStatuses
     */
    public function __construct(
        public string $slug,
        public string $capability,
        public array $allowedStatuses,
    ) {}

    public function allowsStatus(string $status): bool
    {
        return in_array($status, $this->allowedStatuses, true);
    }
}
