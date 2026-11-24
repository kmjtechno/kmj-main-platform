<?php

namespace Tests\Feature;

use App\Http\Responses\ConfirmedPasskeyLoginResponse;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Request;
use Illuminate\Session\Store;
use Laravel\Passkeys\Contracts\PasskeyLoginResponse;
use Tests\TestCase;

final class PasskeyLoginConfirmationTest extends TestCase
{
    use RefreshDatabase;

    public function test_passkey_login_response_is_bound_to_the_confirming_response(): void
    {
        self::assertInstanceOf(ConfirmedPasskeyLoginResponse::class, app(PasskeyLoginResponse::class));
    }

    public function test_successful_passkey_login_records_password_confirmation_once(): void
    {
        $request = Request::create('/passkeys/login', 'POST');
        $request->setLaravelSession($this->app['session']->driver());
        self::assertFalse($request->session()->has('auth.password_confirmed_at'));

        (new ConfirmedPasskeyLoginResponse)->toResponse($request);

        self::assertInstanceOf(Store::class, $request->session());
        self::assertGreaterThan(time() - 5, (int) $request->session()->get('auth.password_confirmed_at'));
    }

    public function test_confirmation_is_not_granted_without_a_login(): void
    {
        $this->get('/operator/products')->assertRedirect('/login');
    }
}
