<?php

declare(strict_types=1);

namespace App\Mail;

use Illuminate\Mail\Mailables\Address;
use Illuminate\Mail\Mailables\Content;
use Illuminate\Mail\Mailables\Envelope;
use Illuminate\Mail\Mailable;

/**
 * Original KMJ-branded plain text + escaped HTML.
 * All sender and recipient identities are derived from the server policy.
 */
final class NativeExternalMailMessage extends Mailable
{
    public function __construct(
        public readonly string $heading,
        public readonly string $messageBody,
        public readonly string $senderAddress,
    ) {}

    public function envelope(): Envelope
    {
        return new Envelope(
            from: new Address($this->senderAddress, 'KMJ TECHNO'),
            subject: $this->heading,
        );
    }

    public function content(): Content
    {
        return new Content(
            view: 'emails.kmj-native-outgoing',
            text: 'emails.kmj-native-outgoing-text',
            with: [
                'heading' => $this->heading,
                'body' => $this->messageBody,
                'senderAddress' => $this->senderAddress,
            ],
        );
    }
}
