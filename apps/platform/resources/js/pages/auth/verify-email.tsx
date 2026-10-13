// Components
import { Form, Head } from '@inertiajs/react';
import TextLink from '@/components/text-link';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import { logout } from '@/routes';
import { send } from '@/routes/verification';

type Props = {
    status?: string;
    mailDeliveryAvailable: boolean;
};

export default function VerifyEmail({
    status,
    mailDeliveryAvailable,
}: Props) {
    return (
        <>
            <Head title="Email verification" />

            {!mailDeliveryAvailable ? (
                <div
                    role="alert"
                    className="mb-5 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-center text-sm text-amber-700 dark:text-amber-300"
                >
                    Verification email delivery is temporarily unavailable.
                    Our team needs to restore the email service. Please try
                    again later or contact support. Repeatedly requesting an
                    email will not help until this is fixed.
                </div>
            ) : status === 'verification-link-sent' ? (
                <div role="status" className="mb-4 text-center text-sm font-medium text-green-600">
                    Your verification email request was accepted. Delivery is
                    not yet confirmed. Check your inbox and spam folder.
                </div>
            ) : (
                <p className="text-muted-foreground mb-5 text-center text-sm">
                    Check your inbox and spam folder for your verification link.
                    Delivery may take a few minutes.
                </p>
            )}

            <Form {...send.form()} className="space-y-6 text-center">
                {({ processing }) => (
                    <>
                        <Button
                            disabled={processing || !mailDeliveryAvailable}
                            variant="secondary"
                        >
                            {processing && <Spinner />}
                            Resend verification email
                        </Button>

                        <TextLink
                            href={logout()}
                            className="mx-auto block text-sm"
                        >
                            Log out
                        </TextLink>
                    </>
                )}
            </Form>
        </>
    );
}

VerifyEmail.layout = {
    title: 'Email verification',
    description:
        'Verify your email address to finish registration. If your message has not arrived, check spam or contact support.',
};
