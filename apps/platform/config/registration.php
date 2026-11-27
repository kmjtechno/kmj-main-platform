<?php

return [
    /*
     * Invisible bot guard for the public /register form: a hidden honeypot field plus an encrypted,
     * one-use, time-stamped form token. No third-party service, no cookie banner, no cost.
     */
    'bot_guard' => [
        'enabled' => (bool) env('REGISTRATION_BOT_GUARD', true),
        // Humans cannot read and fill this form faster than this; scripts usually can.
        'min_seconds' => (int) env('REGISTRATION_BOT_GUARD_MIN_SECONDS', 3),
        // A form left open longer than this must be reloaded.
        'max_seconds' => (int) env('REGISTRATION_BOT_GUARD_MAX_SECONDS', 7200),
        'honeypot_field' => 'website_url',
        'token_field' => 'kmj_form_token',
    ],
];
