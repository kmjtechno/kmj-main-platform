import { Head, router } from '@inertiajs/react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';

type Props = {
    requestId: string;
    clientName: string;
    redirectHost: string;
    scopes: string[];
};

const scopeText: Record<string, string> = {
    'codebridge:read':
        'List your authorized devices, inspect projects, read files, search code and see job results',
    'codebridge:write':
        'Change files in projects you have made writable, and cancel jobs',
    'codebridge:execute':
        'Run the quality-gate commands your administrator configured',
    offline_access: 'Stay connected without asking you to sign in again',
};

export default function OAuthAuthorize({
    requestId,
    clientName,
    redirectHost,
    scopes,
}: Props) {
    const [processing, setProcessing] = useState(false);

    const decide = (decision: 'approve' | 'deny') => {
        setProcessing(true);
        router.post(
            '/oauth/authorize',
            { request_id: requestId, decision },
            { onFinish: () => setProcessing(false) },
        );
    };

    return (
        <>
            <Head title="Connect KMJ CodeBridge" />
            <div className="space-y-6">
                <div className="space-y-2 text-center">
                    <h1 className="text-xl font-semibold">
                        Connect {clientName} to KMJ CodeBridge
                    </h1>
                    <p className="text-sm text-muted-foreground">
                        After you approve, you will be returned to{' '}
                        <strong className="text-foreground">
                            {redirectHost}
                        </strong>
                        . Only approve if you started this from that app.
                    </p>
                </div>

                <div className="space-y-2">
                    <p className="text-sm font-medium">It will be able to:</p>
                    <ul className="list-disc space-y-1 pl-5 text-sm">
                        {scopes.map((scope) => (
                            <li key={scope}>{scopeText[scope] ?? scope}</li>
                        ))}
                    </ul>
                    <p className="text-xs text-muted-foreground">
                        Access is limited to the devices and projects your
                        organization has authorized. You can revoke devices at
                        any time.
                    </p>
                </div>

                <div className="flex gap-3">
                    <Button
                        variant="outline"
                        className="flex-1"
                        disabled={processing}
                        onClick={() => decide('deny')}
                        data-test="oauth-deny"
                    >
                        Cancel
                    </Button>
                    <Button
                        className="flex-1"
                        disabled={processing}
                        onClick={() => decide('approve')}
                        data-test="oauth-approve"
                    >
                        Approve
                    </Button>
                </div>
            </div>
        </>
    );
}
