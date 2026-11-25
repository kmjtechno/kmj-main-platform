<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Models\User;
use App\Services\Mail\OwnerNativeSmtpSettings;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

final class OwnerNativeSmtpController
{
    public function index(Request $request, OwnerNativeSmtpSettings $settings): Response
    {
        return Inertia::render('operator-mail-smtp', [
            'smtp' => $settings->snapshot($this->actor($request)),
        ]);
    }

    public function test(Request $request, OwnerNativeSmtpSettings $settings): RedirectResponse
    {
        $profile = $request->validate(['profile' => ['required', 'in:loopback,brevo']]);
        $settings->test($this->actor($request), (string) $profile['profile']);

        return redirect()->to('/operator/mail/smtp')->with('status', 'Test submission accepted by SMTP. Check your verified inbox; delivery is not yet proven.');
    }

    public function activate(Request $request, OwnerNativeSmtpSettings $settings): RedirectResponse
    {
        $profile = $request->validate(['profile' => ['required', 'in:loopback,brevo']]);
        $settings->activate($this->actor($request), (string) $profile['profile']);

        return redirect()->to('/operator/mail/smtp')->with('status', 'Native mail SMTP profile selected. Transactional mail and inbound routing are unchanged.');
    }

    public function pause(Request $request, OwnerNativeSmtpSettings $settings): RedirectResponse
    {
        $settings->pause($this->actor($request));

        return redirect()->to('/operator/mail/smtp')->with('status', 'Native external sending paused. An already claimed submission may finish.');
    }

    private function actor(Request $request): User
    {
        $actor = $request->user();
        abort_unless($actor instanceof User, 401);

        return $actor;
    }
}
