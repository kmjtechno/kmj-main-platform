<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Models\User;
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
        private readonly PlatformOwnerAccess $owner,
    ) {}

    public function index(Request $request, string $portal): Response
    {
        $user = $this->user($request, $portal);
        $values = $request->validate([
            'folder' => ['sometimes', 'in:inbox,sent,drafts,trash'],
            'q' => ['sometimes', 'nullable', 'string', 'max:80'],
            'message' => ['sometimes', 'integer', 'min:1'],
        ]);
        $folder = (string) ($values['folder'] ?? 'inbox');
        $search = trim((string) ($values['q'] ?? ''));
        $thread = isset($values['message']) ? $this->mail->thread($user, (int) $values['message']) : null;

        return Inertia::render('mail-center', [
            'audience' => $portal === 'operator' ? 'owner' : 'staff',
            'templates' => WorkforceMailCatalog::forAudience($portal === 'operator' ? 'owner' : 'team'),
            'workspaceMode' => 'native_internal',
            'mailbox' => $this->mail->mailbox($user, $folder, $search),
            'folder' => $folder,
            'q' => $search,
            'selectedThread' => $thread,
            'directory' => $this->mail->directory(),
            'staff' => $portal === 'operator' ? $this->mail->activeStaff() : [],
            'myUserId' => (int) $user->getKey(),
            'externalMailEnabled' => false,
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

    public function draft(Request $request, string $portal): RedirectResponse
    {
        $user = $this->user($request, $portal);
        $input = $request->validate([
            'draft_id' => ['sometimes', 'nullable', 'integer', 'min:1'],
            'recipient_id' => ['sometimes', 'nullable', 'integer', 'min:1'],
            'subject' => ['present', 'nullable', 'string', 'max:180'],
            'body' => ['present', 'nullable', 'string', 'max:12000'],
        ]);
        $this->mail->saveDraft($user,
            isset($input['draft_id']) ? (int) $input['draft_id'] : null,
            isset($input['recipient_id']) ? (int) $input['recipient_id'] : null,
            trim((string) $input['subject']), (string) $input['body']);

        return redirect()->to('/'.$portal.'/mail?folder=drafts')
            ->with('status', 'Draft saved in your private KMJ mailbox.');
    }

    public function sendDraft(Request $request, string $portal, int $message): RedirectResponse
    {
        $this->mail->sendDraft($this->user($request, $portal), $message);

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

    public function grantStaff(Request $request): RedirectResponse
    {
        $user = $this->user($request, 'operator');
        $values = $request->validate(['target_user_id' => ['required', 'integer', 'min:1']]);
        $this->mail->grantStaff($user, (int) $values['target_user_id']);

        return redirect()->to('/operator/mail')
            ->with('status', 'Verified account granted KMJ internal staff-mail access.');
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
