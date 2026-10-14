import { router, useForm } from '@inertiajs/react';
import {
    CheckCircle2,
    KeyRound,
    LockKeyhole,
    RotateCcw,
    Save,
    ShieldAlert,
    SlidersHorizontal,
} from 'lucide-react';
import { useState, type FormEvent } from 'react';

export type OwnerGatewaySetting = {
    provider: 'cashfree' | 'razorpay';
    storage_ready: boolean;
    name: string;
    environment: 'sandbox';
    merchant_status:
        | 'not_verified'
        | 'verification_pending'
        | 'owner_reports_approved';
    international_requested: boolean;
    client_id_stored: boolean;
    client_secret_stored: boolean;
    webhook_secret_stored: boolean;
    last_updated: string | null;
    live_charging_enabled: false;
    sandbox_transaction_verified: false;
    note: string;
};

function GatewaySettingsCard({ setting }: { setting: OwnerGatewaySetting }) {
    const [showSecretForm, setShowSecretForm] = useState(false);
    const [revoking, setRevoking] = useState(false);
    const form = useForm({
        environment: 'sandbox',
        merchant_status: setting.merchant_status,
        international_requested: setting.international_requested,
        client_id: '',
        client_secret: '',
        webhook_secret: '',
    });

    const save = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        if (!setting.storage_ready) return;
        form.put(`/operator/payments/gateways/${setting.provider}`, {
            preserveScroll: true,
            onSuccess: () => {
                form.setData((data) => ({
                    ...data,
                    client_id: '',
                    client_secret: '',
                    webhook_secret: '',
                }));
                setShowSecretForm(false);
            },
        });
    };

    const revoke = () => {
        if (!setting.storage_ready) return;
        if (
            !window.confirm(
                `Remove saved sandbox credentials for ${setting.name}? This cannot be undone.`,
            )
        )
            return;
        setRevoking(true);
        router.delete(
            `/operator/payments/gateways/${setting.provider}/credentials`,
            {
                preserveScroll: true,
                onFinish: () => setRevoking(false),
            },
        );
    };

    return (
        <article
            id={`gateway-settings-${setting.provider}`}
            className="scroll-mt-6 rounded-2xl border border-white/10 bg-[#10141b] p-5 sm:p-6"
        >
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <p className="text-xs font-bold tracking-widest text-slate-400 uppercase">
                        Gateway settings
                    </p>
                    <h3 className="mt-1 text-xl font-black">{setting.name}</h3>
                    <p className="mt-2 max-w-md text-xs leading-6 text-slate-400">
                        Store sandbox keys in encrypted server storage. Never
                        paste live keys here.
                    </p>
                </div>
                <span className="rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-1 text-xs font-bold text-blue-200">
                    TEST MODE ONLY
                </span>
            </div>
            <div className="mt-5 grid gap-2 rounded-xl border border-white/10 bg-black/20 p-4 text-xs sm:grid-cols-3">
                <div className="flex items-center gap-2 text-slate-300">
                    <KeyRound className="h-4 w-4" />
                    {setting.client_id_stored
                        ? 'Test key ID saved'
                        : 'Test key ID missing'}
                </div>
                <div className="flex items-center gap-2 text-slate-300">
                    <LockKeyhole className="h-4 w-4" />
                    {setting.client_secret_stored
                        ? 'Secret stored'
                        : 'Secret missing'}
                </div>
                <div className="flex items-center gap-2 text-slate-300">
                    <ShieldAlert className="h-4 w-4" />
                    {setting.webhook_secret_stored
                        ? 'Webhook secret stored'
                        : 'Webhook secret missing'}
                </div>
            </div>

            <form onSubmit={save} className="mt-5 space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                    <label className="block space-y-2 text-xs font-semibold text-slate-300">
                        <span>Merchant onboarding</span>
                        <select
                            className="w-full rounded-lg border border-white/20 bg-[#171c24] px-3 py-3 text-sm text-white"
                            value={form.data.merchant_status}
                            onChange={(e) =>
                                form.setData(
                                    'merchant_status',
                                    e.target
                                        .value as OwnerGatewaySetting['merchant_status'],
                                )
                            }
                        >
                            <option value="not_verified">Not verified</option>
                            <option value="verification_pending">
                                KYC / verification pending
                            </option>
                            <option value="owner_reports_approved">
                                Owner reports approved (unverified)
                            </option>
                        </select>
                    </label>
                    <label className="flex items-center gap-3 rounded-xl border border-white/10 p-4 text-xs font-semibold text-slate-300">
                        <input
                            type="checkbox"
                            className="size-4 accent-red-500"
                            checked={form.data.international_requested}
                            onChange={(e) =>
                                form.setData(
                                    'international_requested',
                                    e.target.checked,
                                )
                            }
                        />
                        International acceptance requested
                    </label>
                </div>
                <button
                    type="button"
                    onClick={() => setShowSecretForm((value) => !value)}
                    aria-expanded={showSecretForm}
                    className="inline-flex items-center gap-2 rounded-lg border border-white/15 px-4 py-2 text-sm font-bold hover:bg-white/10 focus-visible:outline-2 focus-visible:outline-red-500"
                >
                    <SlidersHorizontal className="h-4 w-4" />
                    {showSecretForm
                        ? 'Hide credential fields'
                        : 'Add / rotate sandbox credentials'}
                </button>

                {showSecretForm && (
                    <div className="grid gap-4 rounded-xl border border-white/10 bg-black/20 p-4">
                        <p className="text-xs leading-6 text-amber-200">
                            Fields left empty retain the previous stored value.
                            Secrets are write-only and never shown again. Only
                            approved TEST credentials belong here.
                        </p>
                        {(
                            [
                                [
                                    'client_id',
                                    setting.provider === 'razorpay'
                                        ? 'Razorpay Test Key ID'
                                        : 'Cashfree Sandbox Client ID',
                                ],
                                ['client_secret', 'Sandbox Secret Key'],
                                ['webhook_secret', 'Sandbox Webhook Secret'],
                            ] as const
                        ).map(([key, label]) => (
                            <label
                                key={key}
                                className="space-y-2 text-xs font-semibold text-slate-300"
                            >
                                <span>{label}</span>
                                <input
                                    type={
                                        key === 'client_id'
                                            ? 'text'
                                            : 'password'
                                    }
                                    autoComplete="off"
                                    spellCheck={false}
                                    name={key}
                                    value={form.data[key]}
                                    onChange={(e) =>
                                        form.setData(key, e.target.value)
                                    }
                                    placeholder="Leave blank to keep existing value"
                                    className="w-full rounded-lg border border-white/20 bg-[#171c24] px-3 py-3 text-sm text-white"
                                    maxLength={key === 'client_id' ? 255 : 1024}
                                />
                                {form.errors[key] && (
                                    <span
                                        className="block text-red-300"
                                        role="alert"
                                    >
                                        {form.errors[key]}
                                    </span>
                                )}
                            </label>
                        ))}
                    </div>
                )}
                {!setting.storage_ready && (
                    <p
                        role="status"
                        className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200"
                    >
                        Payment settings storage is pending a verified database
                        migration. Saving is disabled until ready.
                    </p>
                )}
                <div className="flex flex-wrap items-center gap-3">
                    <button
                        type="submit"
                        disabled={form.processing || !setting.storage_ready}
                        className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-red-600 px-5 py-2 text-sm font-bold text-white transition hover:bg-red-500 disabled:opacity-50"
                    >
                        <Save className="h-4 w-4" />
                        {form.processing ? 'Saving…' : 'Save sandbox settings'}
                    </button>
                    <button
                        type="button"
                        onClick={revoke}
                        disabled={
                            revoking ||
                            (!setting.client_id_stored &&
                                !setting.client_secret_stored &&
                                !setting.webhook_secret_stored)
                        }
                        className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-white/20 px-4 py-2 text-xs font-semibold text-slate-300 hover:bg-white/10 disabled:opacity-40"
                    >
                        <RotateCcw className="h-4 w-4" />
                        Remove saved keys
                    </button>
                </div>
                {form.recentlySuccessful && (
                    <p
                        role="status"
                        className="flex items-center gap-2 text-xs text-emerald-300"
                    >
                        <CheckCircle2 className="h-4 w-4" />
                        Configuration stored. Sandbox checkout remains
                        unverified.
                    </p>
                )}
                <p className="text-xs leading-6 text-slate-400">
                    {setting.note}
                    {setting.last_updated
                        ? ` Last changed: ${new Date(setting.last_updated).toLocaleString()}.`
                        : ''}
                </p>
            </form>
        </article>
    );
}

export default function OperatorPaymentSettings({
    gatewaySettings,
    selectedProvider,
}: {
    gatewaySettings: OwnerGatewaySetting[];
    selectedProvider: OwnerGatewaySetting['provider'];
}) {
    const selected = gatewaySettings.find(
        (setting) => setting.provider === selectedProvider,
    );

    return (
        <section
            aria-label="Payment gateway settings"
            className="mx-auto w-full max-w-6xl space-y-5"
            id="gateway-settings"
        >
            <div className="flex flex-col gap-2">
                <p className="text-xs font-black tracking-widest text-red-400 uppercase">
                    Settings · Payments
                </p>
                <h2 className="text-2xl font-black">
                    {selected?.name ?? 'Payment provider'} — secure test
                    credentials
                </h2>
                <p className="max-w-3xl text-sm leading-6 text-slate-300">
                    Configure test keys and onboarding notes for each provider.
                    This is a secure configuration vault, not live payment
                    activation. Merchant approval and successful provider
                    transactions still require verification.
                </p>
            </div>
            {selected ? (
                <div className="max-w-4xl">
                    <GatewaySettingsCard
                        key={selected.provider}
                        setting={selected}
                    />
                </div>
            ) : (
                <p role="alert" className="text-sm text-amber-300">
                    The selected provider is not available. Please refresh the
                    page.
                </p>
            )}
        </section>
    );
}
