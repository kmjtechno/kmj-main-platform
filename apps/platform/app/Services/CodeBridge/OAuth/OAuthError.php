<?php

declare(strict_types=1);

namespace App\Services\CodeBridge\OAuth;

use RuntimeException;

/** An RFC 6749 error. A 302 status means redirect back to the client. */
final class OAuthError extends RuntimeException
{
    public function __construct(
        public readonly string $error,
        public readonly int $status,
        public readonly ?string $redirectUri = null,
        public readonly ?string $state = null,
    ) {
        parent::__construct($error);
    }
}
