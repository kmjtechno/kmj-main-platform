import { usePage } from '@inertiajs/react';

/** Full-page navigation on purpose: the server starts the Google OAuth flow. */
export default function GoogleSignInButton({
    label = 'Continue with Google',
}: {
    label?: string;
}) {
    const { publicSite } = usePage().props;

    if (publicSite?.google_signin_available !== true) {
        return null;
    }

    return (
        <div className="grid gap-3">
            <a
                href="/auth/google/redirect"
                data-test="google-signin"
                className="border-input bg-background hover:bg-accent inline-flex h-10 w-full items-center justify-center gap-2 rounded-md border px-4 text-sm font-medium"
            >
                <svg aria-hidden="true" viewBox="0 0 48 48" className="size-4">
                    <path
                        fill="#EA4335"
                        d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.1C12.4 13.6 17.7 9.5 24 9.5z"
                    />
                    <path
                        fill="#4285F4"
                        d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.3 5.5-4.8 7.2l7.5 5.8c4.4-4.1 7.1-10.1 7.1-17.5z"
                    />
                    <path
                        fill="#FBBC05"
                        d="M10.5 28.7A14.5 14.5 0 0 1 9.5 24c0-1.6.3-3.2.8-4.7l-7.9-6.1A24 24 0 0 0 0 24c0 3.9.9 7.5 2.6 10.8l7.9-6.1z"
                    />
                    <path
                        fill="#34A853"
                        d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.5-5.8c-2.1 1.4-4.8 2.3-8.4 2.3-6.3 0-11.6-4.1-13.5-9.8l-7.9 6.1C6.5 42.6 14.6 48 24 48z"
                    />
                </svg>
                {label}
            </a>
            <p className="text-muted-foreground text-center text-xs">
                Or use your email below. With Google we only read your name and
                verified email.
            </p>
        </div>
    );
}
