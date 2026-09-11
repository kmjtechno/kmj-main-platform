<?php

namespace App\Services\Licensing;

use App\Models\LicenseRevocation;
use Illuminate\Support\Carbon;
use InvalidArgumentException;

final class LicenseRevoker
{
    public function revoke(string $jti, ?string $reason = null): LicenseRevocation
    {
        $jti = trim($jti);

        if ($jti === '') {
            throw new InvalidArgumentException('License jti is required.');
        }

        return LicenseRevocation::query()->firstOrCreate(
            ['jti' => $jti],
            [
                'reason' => $reason,
                'revoked_at' => Carbon::now(),
            ],
        );
    }
}
