<?php

namespace App\Http\Responses;

use Laravel\Passkeys\Http\Responses\PasskeyLoginResponse;

/**
 * A successful passkey sign-in is a fresh WebAuthn ceremony, the same proof the
 * passkey "confirm" flow accepts. Record it as the password confirmation so the
 * owner is not asked for the passkey a second time on password.confirm routes.
 * The confirmation still expires after auth.password_timeout, and it is only
 * recorded after the library has verified the assertion and logged the user in.
 */
final class ConfirmedPasskeyLoginResponse extends PasskeyLoginResponse
{
    public function toResponse($request)
    {
        $request->session()->passwordConfirmed();

        return parent::toResponse($request);
    }
}
