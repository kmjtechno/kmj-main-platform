<?php

declare(strict_types=1);

namespace App\Services\Licensing\OmniDesk;

/**
 * Production implementations must delegate signing to an isolated KMS/HSM.
 *
 * Implementations return the raw 64-byte Ed25519 signature. Private signing
 * material must never be exposed through this interface or persisted by the
 * OmniDesk licensing adapter.
 */
interface OmniDeskSigner
{
    public function kid(): string;

    public function sign(string $canonicalPayload): string;
}
