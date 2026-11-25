import { Head, Link, router, usePage } from '@inertiajs/react';
import { ArrowLeft, Mail, ShieldCheck } from 'lucide-react';
import { useState } from 'react';

type Profile = 'loopback' | 'brevo';

type Smtp = {
    installed: boolean;
    active: string;
    loopback_ready: boolean;
    brevo_ready: boolean;
    brevo_credentials_stored: boolean;
    brevo_server_approved: boolean;
    tested_profile: string | null;
    tested_at: string | null;
    sender: string;
};

export default function OperatorMailSmtp({ smtp }: { smtp: Smtp }) {
    const page = usePage();
    const [profile, setProfile] = useState<Profile>(
        smtp.active === 'brevo' ? 'brevo' : 'loopback',
    );
    const [busy, setBusy] = useState(false);
    const [login, setLogin] = useState('');
    const [password, setPassword] = useState('');
    const ready =
        profile === 'loopback' ? smtp.loopback_ready : smtp.brevo_ready;
    const flash = page.props.flash;
    const status =
        flash &&
        typeof flash === 'object' &&
        'status' in flash &&
        typeof flash.status === 'string'
            ? flash.status
            : null;
    const errors = page.props.errors;
    const error =
        errors && typeof errors === 'object'
            ? Object.values(errors).find((value) => typeof value === 'string')
            : null;

    const submit = (action: 'test' | 'activate' | 'pause') => {
        if (busy) return;
        if (
            action === 'test' &&
            !window.confirm(
                'Send one fixed SMTP test email to your verified account address?',
            )
        )
            return;
        if (
            action === 'activate' &&
            !window.confirm(
                'Select this transport for new KMJ Mail submissions? Old queued messages will not be silently rerouted.',
            )
        )
            return;
        if (
            action === 'pause' &&
            !window.confirm('Pause new native external email submissions?')
        )
            return;

        setBusy(true);
        router.post(
            '/operator/mail/smtp/' + action,
            action === 'pause' ? {} : { profile },
            {
                preserveScroll: true,
                onFinish: () => setBusy(false),
            },
        );
    };

    const saveCredentials = () => {
        if (busy || !login || !password) return;
        setBusy(true);
        router.post(
            '/operator/mail/smtp/credentials',
            { smtp_login: login, password },
            {
                preserveScroll: true,
                onFinish: () => {
                    setBusy(false);
                    setLogin('');
                    setPassword('');
                },
            },
        );
    };

    return (
        <>
            <Head title="KMJ Mail SMTP settings" />
            <div className="mx-auto max-w-5xl space-y-5 p-4 sm:p-6">
                <Link
                    href="/operator/mail"
                    className="text-muted-foreground inline-flex items-center gap-2 text-sm"
                >
                    <ArrowLeft className="size-4" /> Back to KMJ Mail
                </Link>
                <header className="rounded-2xl border border-slate-700 bg-gradient-to-br from-[#0d1827] to-[#301021] p-6 text-white">
                    <Mail className="size-7 text-red-400" />
                    <h1 className="mt-3 text-2xl font-bold">SMTP settings</h1>
                    <p className="mt-2 text-sm text-slate-300">
                        Owner-controlled outbound transport. Existing account
                        verification mail and inbound routing are separate.
                    </p>
                </header>
                {(status || error) && (
                    <p role="status" className="rounded-xl border p-4 text-sm">
                        {error ?? status}
                    </p>
                )}
                <section className="bg-card space-y-5 rounded-2xl border p-5">
                    <div className="grid gap-4 sm:grid-cols-2">
                        <div>
                            <p className="text-muted-foreground text-xs">
                                Active transport
                            </p>
                            <strong className="mt-1 block text-lg">
                                {smtp.active === 'loopback'
                                    ? 'Elite Postfix'
                                    : smtp.active === 'brevo'
                                      ? 'Brevo SMTPS'
                                      : 'Paused / unavailable'}
                            </strong>
                        </div>
                        <div>
                            <p className="text-muted-foreground text-xs">
                                Configured domain sender
                            </p>
                            <strong className="mt-1 block break-all">
                                {smtp.sender || 'Not configured'}
                            </strong>
                        </div>
                    </div>
                    <label className="block text-sm font-semibold">
                        SMTP provider
                        <select
                            className="bg-background mt-2 block min-h-11 w-full rounded-xl border px-3"
                            value={profile}
                            onChange={(event) =>
                                setProfile(event.target.value as Profile)
                            }
                        >
                            <option value="loopback">
                                KMJ Elite Postfix (primary)
                            </option>
                            <option value="brevo">
                                Brevo SMTPS (optional)
                            </option>
                        </select>
                    </label>
                    <div className="grid gap-3 text-sm sm:grid-cols-2">
                        <div className="rounded-xl border p-3">
                            <p className="text-muted-foreground text-xs">
                                SMTP host
                            </p>
                            <strong>
                                {profile === 'loopback'
                                    ? '127.0.0.1'
                                    : 'smtp-relay.brevo.com'}
                            </strong>
                        </div>
                        <div className="rounded-xl border p-3">
                            <p className="text-muted-foreground text-xs">
                                Port and encryption
                            </p>
                            <strong>
                                {profile === 'loopback'
                                    ? '25 · Local only'
                                    : '465 · Implicit TLS'}
                            </strong>
                        </div>
                        <div className="rounded-xl border p-3">
                            <p className="text-muted-foreground text-xs">
                                Authentication
                            </p>
                            <strong>
                                {profile === 'loopback'
                                    ? 'No credentials on local hop'
                                    : smtp.brevo_credentials_stored
                                      ? 'Encrypted owner credentials'
                                      : 'Server-provisioned credentials'}
                            </strong>
                        </div>
                        <div className="rounded-xl border p-3">
                            <p className="text-muted-foreground text-xs">
                                Configuration status
                            </p>
                            <strong>
                                {ready ? 'Ready to test' : 'Not ready'}
                            </strong>
                        </div>
                    </div>
                    {profile === 'brevo' && (
                        <form
                            className="space-y-3 rounded-xl border p-4"
                            onSubmit={(event) => {
                                event.preventDefault();
                                saveCredentials();
                            }}
                        >
                            <h2 className="text-sm font-bold">
                                Brevo SMTP credentials
                            </h2>
                            <p className="text-muted-foreground text-xs">
                                {smtp.brevo_server_approved
                                    ? 'Server provider approval is present.'
                                    : 'Server provider approval is still required.'}
                                Pause or select local SMTP before rotation.
                            </p>
                            <label className="block text-xs">
                                SMTP login
                                <input
                                    type="password"
                                    autoComplete="off"
                                    value={login}
                                    maxLength={254}
                                    onChange={(event) =>
                                        setLogin(event.target.value)
                                    }
                                    className="bg-background mt-1 block min-h-10 w-full rounded-lg border px-3"
                                />
                            </label>
                            <label className="block text-xs">
                                SMTP password / key
                                <input
                                    type="password"
                                    autoComplete="new-password"
                                    value={password}
                                    maxLength={1024}
                                    onChange={(event) =>
                                        setPassword(event.target.value)
                                    }
                                    className="bg-background mt-1 block min-h-10 w-full rounded-lg border px-3"
                                />
                            </label>
                            <button
                                type="submit"
                                disabled={
                                    busy ||
                                    !smtp.installed ||
                                    smtp.active === 'brevo' ||
                                    !login ||
                                    !password
                                }
                                className="rounded-lg border px-3 py-2 text-sm font-semibold disabled:opacity-40"
                            >
                                Save encrypted credentials
                            </button>
                        </form>
                    )}
                    <p className="text-muted-foreground text-sm">
                        Passwords and keys are never returned to the browser.
                        Remote SMTP requires a server-approved provider account.
                        Do not activate a paid plan.
                    </p>
                    {smtp.tested_profile && (
                        <p className="rounded-xl border p-3 text-sm">
                            Last accepted test: {smtp.tested_profile} ·{' '}
                            {smtp.tested_at}. Check the real inbox separately.
                            Activation requires a fresh test on the same
                            profile.
                        </p>
                    )}
                    <div className="flex flex-wrap gap-3">
                        <button
                            type="button"
                            disabled={busy || !smtp.installed || !ready}
                            onClick={() => submit('test')}
                            className="rounded-xl border px-4 py-3 text-sm font-semibold disabled:opacity-40"
                        >
                            Send test email
                        </button>
                        <button
                            type="button"
                            disabled={
                                busy ||
                                !smtp.installed ||
                                !ready ||
                                smtp.tested_profile !== profile
                            }
                            onClick={() => submit('activate')}
                            className="rounded-xl bg-red-600 px-4 py-3 text-sm font-semibold text-white disabled:opacity-40"
                        >
                            Activate tested profile
                        </button>
                        <button
                            type="button"
                            disabled={busy || !smtp.installed}
                            onClick={() => submit('pause')}
                            className="rounded-xl border px-4 py-3 text-sm font-semibold disabled:opacity-40"
                        >
                            Pause sending
                        </button>
                    </div>
                </section>
                <div className="bg-card flex gap-3 rounded-xl border p-4">
                    <ShieldCheck className="size-5 shrink-0 text-red-400" />
                    <p className="text-muted-foreground text-sm">
                        SMTP acceptance is not recipient inbox delivery.
                        Changing profiles never retries unknown submissions or
                        automatically switches existing messages to a new
                        provider. Incoming email routing is independent.
                    </p>
                </div>
            </div>
        </>
    );
}
