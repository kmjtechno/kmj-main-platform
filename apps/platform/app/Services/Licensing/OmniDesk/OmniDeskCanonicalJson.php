<?php

declare(strict_types=1);

namespace App\Services\Licensing\OmniDesk;

use DomainException;
use JsonException;

final class OmniDeskCanonicalJson
{
    /**
     * Encode the exact canonical JSON form consumed by the OmniDesk Rust
     * verifier: object keys sorted lexicographically, list order preserved,
     * no insignificant whitespace.
     *
     * @param  array<string, mixed>  $payload
     */
    public function encode(array $payload): string
    {
        try {
            return json_encode(
                $this->normalize($payload),
                JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE,
            );
        } catch (JsonException) {
            throw new DomainException('OMNIDESK_ENTITLEMENT_PAYLOAD_INVALID');
        }
    }

    private function normalize(mixed $value): mixed
    {
        if (!is_array($value)) {
            return $value;
        }

        if (array_is_list($value)) {
            return array_map(fn (mixed $entry): mixed => $this->normalize($entry), $value);
        }

        ksort($value, SORT_STRING);

        foreach ($value as $key => $entry) {
            if (! is_string($key)) {
                throw new DomainException('OMNIDESK_ENTITLEMENT_PAYLOAD_INVALID');
            }

            $value[$key] = $this->normalize($entry);
        }

        return $value;
    }
}
