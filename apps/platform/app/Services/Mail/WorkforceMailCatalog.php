<?php

namespace App\Services\Mail;

use Illuminate\Notifications\Messages\MailMessage;
use InvalidArgumentException;

/**
 * First-party template catalog for owner and organization-team mail.
 * These are preview-ready templates, not proof that staff invitations,
 * support cases, approval queues or Gmail OAuth exist in production.
 */
final class WorkforceMailCatalog
{
    /** @return list<array{kind:string,category:string,subject:string,heading:string,intro:string,notice:string}> */
    public static function forAudience(string $audience): array
    {
        if (! in_array($audience, ['owner', 'team'], true)) {
            throw new InvalidArgumentException('Unsupported mail audience.');
        }

        return array_values(array_filter(
            self::templates(),
            static fn (array $item): bool => $item['audience'] === $audience,
        ));
    }

    /**
     * @return list<array{kind:string,audience:string,category:string,subject:string,heading:string,intro:string,notice:string}>
     */
    private static function templates(): array
    {
        return [
            [
                'kind' => 'owner_briefing',
                'audience' => 'owner',
                'category' => 'OWNER OPERATIONS',
                'subject' => 'Your KMJ operations briefing | KMJ TECHNO',
                'heading' => 'Clarity for the decisions ahead.',
                'intro' => 'Your operating overview is ready to review in the secure KMJ Command Center. Every metric must be backed by verified source data.',
                'notice' => 'Do not interpret this email as proof that scheduled operations, backups, deliveries or releases have passed.',
            ],
            [
                'kind' => 'owner_approval',
                'audience' => 'owner',
                'category' => 'APPROVALS',
                'subject' => 'A decision needs review | KMJ TECHNO',
                'heading' => 'A decision is awaiting review.',
                'intro' => 'An authorized workflow has requested an owner decision. Open KMJ TECHNO directly to inspect the evidence and applicable approval gates.',
                'notice' => 'An email does not grant authority or approve a release. Confirm sensitive actions inside the protected platform.',
            ],
            [
                'kind' => 'owner_security',
                'audience' => 'owner',
                'category' => 'SECURITY',
                'subject' => 'Review account security | KMJ TECHNO',
                'heading' => 'Security deserves attention.',
                'intro' => 'A security signal needs an independent review. Inspect the official security workspace and only act on verified evidence.',
                'notice' => 'No passwords, OTPs, private links, recovery codes or signing keys will ever be included.',
            ],
            [
                'kind' => 'owner_mail_health',
                'audience' => 'owner',
                'category' => 'MAIL DELIVERY',
                'subject' => 'Mail delivery needs review | KMJ TECHNO',
                'heading' => 'Keep every customer informed.',
                'intro' => 'A mail-delivery signal requires review. Look for independently verified acceptance, deferrals, bounces and service readiness.',
                'notice' => 'A queue length of zero or an accepted send request is not proof of recipient inbox delivery.',
            ],
            [
                'kind' => 'owner_order_review',
                'audience' => 'owner',
                'category' => 'COMMERCE',
                'subject' => 'An order needs review | KMJ TECHNO',
                'heading' => 'An order awaits your review.',
                'intro' => 'A customer order may need an authorized decision. Review its lifecycle and verified payment evidence in the owner console.',
                'notice' => 'Requested orders are not confirmed payments, and confirmed payments do not automatically issue licenses.',
            ],
            [
                'kind' => 'team_welcome',
                'audience' => 'team',
                'category' => 'TEAM ACCESS',
                'subject' => 'Welcome to your KMJ workspace | KMJ TECHNO',
                'heading' => 'Your workspace, ready when you are.',
                'intro' => 'Welcome. Your organization workspace brings together the services and information permitted by your current membership.',
                'notice' => 'Your permissions are organization-scoped. This message does not grant KMJ platform-owner or internal staff privileges.',
            ],
            [
                'kind' => 'team_access',
                'audience' => 'team',
                'category' => 'ACCOUNT ACCESS',
                'subject' => 'Your workspace access was updated | KMJ TECHNO',
                'heading' => 'Your access has an update.',
                'intro' => 'Your organization access may have changed. Sign in to review your current membership and available actions.',
                'notice' => 'Access changes must be verified against the organization membership ledger; an email never creates a role or entitlement.',
            ],
            [
                'kind' => 'team_assignment',
                'audience' => 'team',
                'category' => 'WORKFLOW',
                'subject' => 'A task needs your attention | KMJ TECHNO',
                'heading' => 'Your next action, clearly defined.',
                'intro' => 'A workflow can notify you when a task is assigned to you. Open your workspace to verify the assignment and its permitted next step.',
                'notice' => 'This is a preview of future task notifications. No assignment is created or implied by the template.',
            ],
            [
                'kind' => 'team_support',
                'audience' => 'team',
                'category' => 'SUPPORT',
                'subject' => 'Support case update | KMJ TECHNO',
                'heading' => 'A support update you can act on.',
                'intro' => 'When an authorized support case changes, the permitted team member can receive a concise update and review the case in context.',
                'notice' => 'Support-case access and recipient authorization must be checked before any real case content is emailed.',
            ],
            [
                'kind' => 'team_security',
                'audience' => 'team',
                'category' => 'ACCOUNT SECURITY',
                'subject' => 'Account security reminder | KMJ TECHNO',
                'heading' => 'Keep your account secure.',
                'intro' => 'Review your password, passkeys and active sessions in your secure account settings when appropriate.',
                'notice' => 'No one at KMJ TECHNO will ask for your password, OTP or recovery code by email.',
            ],
        ];
    }

    public static function previewMessage(string $kind, string $audience, string $recipientName): MailMessage
    {
        $match = null;
        foreach (self::forAudience($audience) as $item) {
            if ($item['kind'] === $kind) {
                $match = $item;
                break;
            }
        }
        if ($match === null) {
            throw new InvalidArgumentException('This mail template is outside the authorized audience.');
        }
        $recipientName = trim($recipientName);
        if ($recipientName === '' || mb_strlen($recipientName) > 100 || strpbrk($recipientName, "\r\n") !== false) {
            throw new InvalidArgumentException('Invalid recipient display name.');
        }

        $subject = '[TEST PREVIEW] '.$match['subject'];
        return (new MailMessage)
            ->subject($subject)
            ->view([
                'html' => 'emails.kmj-transactional',
                'text' => 'emails.kmj-transactional-text',
            ], [
                'subject' => $subject,
                'preheader' => 'KMJ TECHNO preview only. No production event or role change occurred.',
                'eyebrow' => 'PREVIEW / NO ACTION REQUIRED',
                'category' => $match['category'],
                'heading' => $match['heading'],
                'greeting' => 'Hello '.$recipientName.',',
                'intro' => $match['intro'],
                'notice' => 'This is a TEST PREVIEW, not a real approval, case assignment, alert or account access change. '.$match['notice'],
                'details' => [
                    ['label' => 'Message status', 'value' => 'Test preview only'],
                    ['label' => 'Audience', 'value' => $audience === 'owner' ? 'Platform Owner' : 'My organization account'],
                ],
                'actionUrl' => null,
                'actionText' => null,
            ]);
    }
}
