<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class KmjMailPreviewTest extends TestCase
{
    use RefreshDatabase;

    public function test_guest_cannot_view_mail_preview(): void
    {
        $this->get('/internal/kmj-mail-preview')
            ->assertRedirect(route('login'));
    }

    public function test_verified_user_only_sees_disabled_empty_mail_preview(): void
    {
        $user = User::factory()->create();

        $this->actingAs($user)
            ->get('/internal/kmj-mail-preview')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('mail/index')
                ->where('transportStatus', 'not_configured')
                ->where('account', null)
                ->where('messages', []));
    }

    public function test_unverified_user_cannot_view_mail_preview(): void
    {
        $user = User::factory()->unverified()->create();

        $this->actingAs($user)
            ->get('/internal/kmj-mail-preview')
            ->assertRedirect(route('verification.notice'));
    }
}
