<?php

declare(strict_types=1);

namespace App\Services\Licensing\OmniDesk;

use DomainException;

final readonly class OmniDeskApiPrincipal
{
    public function __construct(
        public string $actorId,
        public string $organizationId,
        public bool $canManage,
    ) {
        if (trim($this->actorId) === '' || trim($this->organizationId) === '') {
            throw new DomainException('OMNIDESK_UNAUTHENTICATED');
        }
    }
}
