<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Models\User;
use App\Services\Mail\NativeExternalMailService;
use App\Services\Mail\NativeMailService;
use App\Services\Mail\RegistrationMailReadiness;
use App\Services\Mail\WorkforceMailActions;
use App\Services\Mail\WorkforceMailCatalog;
use App\Services\PlatformOwnerAccess;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

final class NativeMailController
{
    public function __construct(
        private readonly NativeMailService $mail,
        private readonly NativeExternalMailService $external,
        private readonly PlatformOwnerAccess $owner,
    ) {}

    public function index(Request $request, string $portal): Response
    {
        $user = $this->user($request, $portal);
        $values = $request->validate([
            'folder' => ['sometimes', 'in:inbox,sent,drafts,archive,starred,trash'],
            'q' => ['sometimes', 'nullable', 'string', 'max:80'],
            'message' => ['sometimes', 'integer', 'min:1'],
            'page' => ['sometimes', 'integer', 'min:1', 'max:1000'],
        ]);
        $folder = (string) ($values['folder'] ?? 'inbox');
        $search = trim((string) ($values['q'] ?? ''));
        $thread = isset($values['message']) ? $this->mail->thread($user, (int) $values['message']) : null;
        $mailbox = $this->mail->mailbox($user, $folder, $search, (int) ($values['page'] ?? 1));
        // Show a clearly labeled preview of this same user's Sent records when
        // Inbox is empty. Never fabricate Inbox mail, cross-tenant records or
        // inferred recipient delivery; search/filter views keep their true empty state.
        $recentSent = $folder === 'inbox' && $search === '' && $mailbox['total'] === 0
            ? $this->mail->mailbox($user, 'sent', '', 1)
            : null;

        return Inertia::render('mail-center', [
            'audience' => $portal === 'operator' ? 'owner' : 'staff',
            'templates' => WorkforceMailCatalog::forAudience($portal === 'operator' ? 'owner' : 'team'),
            'workspaceMode' => 'native_internal',
            'mailbox' => $mailbox,
            'recentSent' => $recentSent === null ? null : [
                'total' => $recentSent['total'],
                'items' => array_slice($recentSent['items'], 0, 6),
            ],
            'mailMetrics' => $this->mail->summary($user),
            'folder' => $folder,
            'q' => $search,
            'selectedThread' => $thread,
            'selectedMessageId' => isset($values['message']) ? (int) $values['message'] : null,
            'directory' => $this->mail->directory(),
            'staff' => $portal === 'operator' ? $this->mail->activeStaff() : [],
            'myUserId' => (int) $user->getKey(),
            'externalMailEnabled' => $this->external->transportEnabled(),
            'externalOutbound' => $this->external->capability($user),
            'transportCanAttempt' => app(RegistrationMailReadiness::class)->canAttemptDelivery(),
            'testEnabled' => config('services.kmj_workforce_mail.preview_enabled', false) === true,
        ]);
    }

    public function send(Request $request, string $portal): RedirectResponse
    {
        $user = $this->user($request, $portal);
        $input = $request->validate([
            'recipient_id' => ['required', 'integer', 'min:1'],
            'subject' => ['required', 'string', 'min:1', 'max:180'],
            'body' => ['required', 'string', 'min:1', 'max:12000'],
            'client_key' => ['required', 'uuid'],
            'reply_to_id' => ['sometimes', 'nullable', 'integer', 'min:1'],
        ]);
        $this->mail->send($user, (int) $input['recipient_id'],
            trim((string) $input['subject']), trim((string) $input['body']),
            (string) $input['client_key'],
            isset($input['reply_to_id']) ? (int) $input['reply_to_id'] : null);

        return redirect()->to('/'.$portal.'/mail?folder=sent')
            ->with('status', 'Delivered to the recipient’s KMJ private inbox. No external email was sent.');
    }

    public function sendExternal(Request $request, string $portal): RedirectResponse
    {
        $user = $this->user($request, $portal);
        $input = $request->validate([
            'recipient_email' => ['required', 'email', 'max:254'],
            'subject' => ['required', 'string', 'min:1', 'max:180'],
            'body' => ['required', 'string', 'min:1', 'max:12000'],
            'client_key' => ['required', 'uuid'],
            'reply_to_id' => ['sometimes', 'nullable', 'integer', 'min:1'],
        ]);
        $this->external->queue(
            $user,
            (string) $input['recipient_email'],
            (string) $input['subject'],
            (string) $input['body'],
            (string) $input['client_key'],
            isset($input['reply_to_id']) ? (int) $input['reply_to_id'] : null,
        );

        return redirect()->to('/'.$portal.'/mail?folder=sent')
            ->with('status', 'Queued for KMJ SMTP submission. Mail-server acceptance and recipient inbox delivery are separate statuses.');
    }

    public function draft(Request $request, string $portal): RedirectResponse
    {
        $user = $this->user($request, $portal);
        $input = $request->validate([
            'draft_id' => ['sometimes', 'nullable', 'integer', 'min:1'],
            'recipient_id' => ['sometimes', 'nullable', 'integer', 'min:1'],
            'recipient_type' => ['sometimes', 'in:internal,external'],
            'recipient_email' => ['sometimes', 'nullable', 'email', 'max:254'],
            'subject' => ['present', 'nullable', 'string', 'max:180'],
            'body' => ['present', 'nullable', 'string', 'max:12000'],
        ]);
        if (($input['recipient_type'] ?? 'internal') === 'external') {
            $this->external->saveDraft(
                $user,
                isset($input['draft_id']) ? (int) $input['draft_id'] : null,
                isset($input['recipient_email']) ? (string) $input['recipient_email'] : null,
                trim((string) $input['subject']),
                (string) $input['body'],
            );
        } else {
            $this->mail->saveDraft($user,
                isset($input['draft_id']) ? (int) $input['draft_id'] : null,
                isset($input['recipient_id']) ? (int) $input['recipient_id'] : null,
                trim((string) $input['subject']), (string) $input['body']);
        }

        return redirect()->to('/'.$portal.'/mail?folder=drafts')
            ->with('status', 'Draft saved in your private KMJ mailbox.');
    }

    public function sendDraft(Request $request, string $portal, int $message): RedirectResponse
    {
        $user = $this->user($request, $portal);
        if ($this->external->isExternalDraft($user, $message)) {
            $this->external->sendDraft($user, $message);

            return redirect()->to('/'.$portal.'/mail?folder=sent')
                ->with('status', 'External draft queued for KMJ mail-server submission. Recipient delivery is not confirmed.');
        }

        $this->mail->sendDraft($user, $message);

        return redirect()->to('/'.$portal.'/mail?folder=sent')
            ->with('status', 'Draft delivered to the recipient’s KMJ private inbox.');
    }

    public function trash(Request $request, string $portal, int $message): RedirectResponse
    {
        $this->mail->moveToTrash($this->user($request, $portal), $message);

        return redirect()->to('/'.$portal.'/mail?folder=trash')
            ->with('status', 'Message moved to your Trash. Other mailboxes remain unchanged.');
    }

    public function restore(Request $request, string $portal, int $message): RedirectResponse
    {
        $this->mail->moveToTrash($this->user($request, $portal), $message, true);

        return redirect()->to('/'.$portal.'/mail')
            ->with('status', 'Message restored to its previous folder.');
    }

    public function manage(Request $request, string $portal): RedirectResponse
    {
        $user = $this->user($request, $portal);
        $values = $request->validate([
            'ids' => ['required', 'array', 'min:1', 'max:40'],
            'ids.*' => ['required', 'integer', 'distinct', 'min:1'],
            'action' => ['required', 'in:star,unstar,read,unread,archive,unarchive,trash,restore'],
            'folder' => ['sometimes', 'in:inbox,sent,drafts,archive,starred,trash'],
        ]);
        $count = $this->mail->manage($user, $values['ids'], (string) $values['action']);
        $folder = (string) ($values['folder'] ?? 'inbox');

        return redirect()->to('/'.$portal.'/mail?folder='.$folder)
            ->with('status', $count.' KMJ Mail message(s) updated. Other users’ copies were not changed.');
    }

    public function grantStaff(Request $request): RedirectResponse
    {
        $user = $this->user($request, 'operator');
        $values = $request->validate(['target_user_id' => ['required', 'integer', 'min:1']]);
        $this->mail->grantStaff($user, (int) $values['target_user_id']);

        return redirect()->to('/operator/mail')
            ->with('status', 'Verified account granted KMJ internal staff-mail access.');
    }

    public function setStaffSenderAlias(Request $request, int $userId): RedirectResponse
    {
        $owner = $this->user($request, 'operator');
        $values = $request->validate([
            'sender_alias' => ['sometimes', 'nullable', 'email', 'max:254'],
        ]);
        $alias = isset($values['sender_alias']) ? (string) $values['sender_alias'] : null;
        $this->external->grantStaffAlias($owner, $userId, $alias);

        return redirect()->to('/operator/mail')
            ->with('status', $alias === null ? 'Staff sender alias cleared.' : 'Staff sender alias assigned for guarded KMJ domain sending.');
    }

    public function revokeStaff(Request $request, int $userId): RedirectResponse
    {
        $this->mail->revokeStaff($this->user($request, 'operator'), $userId);

        return redirect()->to('/operator/mail')
            ->with('status', 'KMJ internal staff-mail access revoked.');
    }

    public function preview(Request $request, string $portal): RedirectResponse
    {
        $user = $this->user($request, $portal);
        app(WorkforceMailActions::class)->previewToSelf($request, $user,
            $portal === 'operator' ? 'owner' : 'team');

        return redirect()->to('/'.$portal.'/mail')
            ->with('status', 'Test email queued for processing; external inbox receipt is not proven.');
    }

    private function user(Request $request, string $portal): User
    {
        abort_unless(in_array($portal, ['operator', 'team'], true), 404);
        $user = $request->user();
        abort_unless($user instanceof User, 401);
        if ($portal === 'operator') {
            $this->owner->require($user);
        } else {
            abort_unless($this->mail->staffAllowed($user), 403);
        }

        return $user;
    }
}
