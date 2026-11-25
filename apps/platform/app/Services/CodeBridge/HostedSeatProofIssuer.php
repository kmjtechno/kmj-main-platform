<?php

declare(strict_types=1);

namespace App\Services\CodeBridge;

use App\Models\User;
use App\Services\Licensing\Kslp\KslpCodec;
use App\Services\Licensing\Kslp\KslpKeyRegistry;
use App\Services\Licensing\Kslp\KslpSigner;
use DomainException;

/**
 * Internal source-only signer for an existing recorded assignment.
 * This does not allocate a seat, establish commercial entitlement, or expose
 * an endpoint. A future caller must enforce verified commercial fulfillment.
 */
final class HostedSeatProofIssuer
{
    public function __construct(
        private readonly HostedSeatAssignmentReader $assignments,
        private readonly HostedSeatAuthorization $authorization,
        private readonly KslpKeyRegistry $keys,
    ) {}

    public function issueForMember(User $actor, string $organization, string $seat, KslpSigner $signer, string $trustedKid): string
    {
        $assignment = $this->assignments->forMember($actor, $organization, $seat);
        if ($assignment === null) {
            throw new DomainException('CODEBRIDGE_SEAT_ASSIGNMENT_REQUIRED');
        }

        $now = now()->getTimestamp();
        if ($signer->kid() !== $trustedKid || preg_match('/\A[A-Za-z0-9_-]{1,128}\z/D', $trustedKid) !== 1) {
            throw new DomainException('CODEBRIDGE_SEAT_SIGNER_INVALID');
        }

        // Refuse unknown, revoked or foreign-product keys before signing.
        $this->keys->publicKey($trustedKid, 'license', 'KMJ_CODEBRIDGE');

        $claims = [
            ...$assignment,
            'protocol_version' => 'KSLP-seat-v1',
            'aud' => 'kmj-codebridge-hosted-seat',
            'product' => 'KMJ_CODEBRIDGE',
            'plan' => 'team',
            'iat' => $now,
            'nbf' => $now,
            'exp' => $now + 300,
        ];
        $proof = KslpCodec::encode($claims, $trustedKid, fn (string $message): string => $signer->sign($message));

        // Re-read the assignment and verify the actual signature against
        // the current product-scoped registry, not the signer's own key.
        if ($this->authorization->subjectForMember($actor, $organization, $seat, $proof, $trustedKid) !== 'seat:'.$seat) {
            throw new DomainException('CODEBRIDGE_SEAT_PROOF_REJECTED');
        }

        return $proof;
    }
}
