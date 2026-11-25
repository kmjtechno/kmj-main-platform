<?php

declare(strict_types=1);

namespace App\Services\CodeBridge;

use App\Models\User;
use App\Services\Licensing\Kslp\KslpKeyRegistry;
use DomainException;

/**
 * Internal, read-only composition of current assignment and signed proof.
 * The pinned kid comes from trusted server policy, never the client.
 * No payment, reservation, issuance or gateway dispatch is enabled here.
 */
final class HostedSeatAuthorization
{
    public function __construct(
        private readonly HostedSeatAssignmentReader $assignments,
        private readonly HostedSeatProofVerifier $proofs,
        private readonly KslpKeyRegistry $keys,
    ) {}

    public function subjectForMember(User $actor, string $organization, string $seat, string $proof, string $trustedKid): ?string
    {
        $assignment = $this->assignments->forMember($actor, $organization, $seat);
        if ($assignment === null) {
            return null;
        }

        try {
            $publicKey = $this->keys->publicKey($trustedKid, 'license', 'KMJ_CODEBRIDGE');
        } catch (DomainException) {
            return null;
        }

        if (! $this->proofs->verifyTrusted($proof, $assignment, $trustedKid, base64_encode($publicKey), now()->getTimestamp())) {
            return null;
        }

        return 'seat:'.$assignment['seat_id'];
    }
}
