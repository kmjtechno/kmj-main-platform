import { useForm } from '@inertiajs/react';
import type { FormEvent } from 'react';
import {
    ArrowRight,
    CheckCircle2,
    CircleAlert,
    ExternalLink,
    KeyRound,
    LockKeyhole,
    ShieldCheck,
} from 'lucide-react';
import type { OwnerGatewaySetting } from '@/components/operator-payment-settings';

type Provider = OwnerGatewaySetting['provider'];

const providers: Record<
    Provider,
    { name: string; dashboard: string; docs: string; dashboardLabel: string }
> = {
    razorpay: {
        name: 'Razorpay',
        dashboard: 'https://dashboard.razorpay.com/app/account-settings',
        docs: 'https://razorpay.com/docs/payments/dashboard/account-settings/api-keys/',
        dashboardLabel: 'Open Razorpay Account & Settings',
    },
    cashfree: {
        name: 'Cashfree Payments',
        dashboard: 'https://merchant.cashfree.com/merchant/pg#api-key',
        docs: 'https://www.cashfree.com/docs/payments/overview',
        dashboardLabel: 'Open Cashfree Merchant API Keys',
    },
};

function SetupStage({
    done,
    label,
    detail,
}: {
    done: boolean;
    label: string;
    detail: string;
}) {
    return (
        <li className="flex items-start gap-3 rounded-xl border border-white/10 bg-black/15 px-4 py-3">
            {done ? (
                <CheckCircle2
                    className="mt-0.5 size-5 shrink-0 text-emerald-400"
                    aria-label="Complete"
                />
            ) : (
                <CircleAlert
                    className="mt-0.5 size-5 shrink-0 text-amber-400"
                    aria-label="Not verified"
                />
            )}
            <div>
                <p className="text-sm font-semibold text-white">{label}</p>
                <p className="mt-1 text-xs leading-5 text-slate-400">{detail}</p>
            </div>
        </li>
    );
}

export default function PaymentGatewayOnboarding({
    gatewaySettings,
    provider,
    onProviderChange,
}: {
    gatewaySettings: OwnerGatewaySetting[];
    provider: Provider;
    onProviderChange: (provider: Provider) => void;
}) {
    const probe = useForm({ test_phone: '' });
    const testConnection = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        if (!keysSaved || probe.processing) return;
        probe.post(`/operator/payments/gateways/${provider}/test-connection`, {
            preserveScroll: true,
            onSuccess: () => probe.reset(),
        });
    };
    const selected = gatewaySettings.find((item) => item.provider === provider);
    const config = providers[provider];
    const keysSaved = Boolean(
        selected?.storage_ready &&
            selected?.client_id_stored &&
            selected?.client_secret_stored,
    );
    const webhookSecretSaved = selected?.webhook_secret_stored === true;
    const savedCount = Number(keysSaved) + Number(webhookSecretSaved);

    return (
        <section
            aria-label="Guided payment gateway onboarding"
            className="mx-auto w-full max-w-6xl rounded-2xl border border-red-500/20 bg-[#11151d] p-5 sm:p-7"
            id="gateway-onboarding"
        >
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <p className="text-xs font-black tracking-widest text-red-400 uppercase">
                        Razorpay + Cashfree · Secure owner setup
                    </p>
                    <h2 className="mt-2 text-2xl font-black text-white">
                        Connect payments in one place
                    </h2>
                    <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">
                        Start in the merchant dashboard, save TEST credentials
                        securely in KMJ, and track missing verification. No
                        OAuth connection to either payment provider exists
                        yet—keys must be entered by the authenticated owner.
                    </p>
                </div>
                <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs font-bold text-amber-200">
                    Sandbox setup only · live checkout locked
                </span>
            </div>

            <div
                className="mt-6 flex flex-wrap gap-2"
                role="group"
                aria-label="Choose payment provider"
            >
                {(['razorpay', 'cashfree'] as const).map((id) => (
                    <button
                        key={id}
                        type="button"
                        aria-pressed={provider === id}
                        onClick={() => {
                            onProviderChange(id);
                            probe.clearErrors();
                            probe.reset();
                        }}
                        className={
                            provider === id
                                ? 'rounded-xl bg-red-600 px-5 py-3 text-sm font-bold text-white'
                                : 'rounded-xl border border-white/15 px-5 py-3 text-sm font-bold text-slate-200 hover:bg-white/10'
                        }
                    >
                        {providers[id].name}
                    </button>
                ))}
            </div>

            <div className="mt-5 flex flex-wrap items-center gap-3 text-sm">
                <span className="font-semibold text-white">
                    {config.name} readiness
                </span>
                <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-300">
                    {savedCount}/2 credential items stored (not payment verification)
                </span>
                <span className="text-xs text-slate-400">
                    Storage is {selected?.storage_ready ? 'ready' : 'not yet migrated'}
                </span>
            </div>

            <ol className="mt-4 grid gap-3 lg:grid-cols-2">
                <SetupStage
                    done={selected?.merchant_status === 'owner_reports_approved'}
                    label="1. Review merchant account"
                    detail="Owner-reported approval is not a verified provider API check. Confirm Test Mode in the provider dashboard."
                />
                <SetupStage
                    done={Boolean(keysSaved)}
                    label="2. Save test API credentials"
                    detail="Only encrypted sandbox keys. Enter them directly in the protected KMJ Super Admin form—never share them in AI chats."
                />
                <SetupStage
                    done={webhookSecretSaved}
                    label="3. Store sandbox webhook secret"
                    detail="A stored secret does NOT mean a webhook endpoint or payment-event reconciliation is configured."
                />
                <SetupStage
                    done={false}
                    label="4. Sandbox payment + license acceptance"
                    detail="Pending: provider order, webhook signature, capture confirmation, ledger reconciliation, refund handling and signed license checks."
                />
            </ol>

            <div className="mt-5 flex flex-wrap gap-3">
                <a
                    href={config.dashboard}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-red-600 px-4 py-2 text-sm font-bold text-white hover:bg-red-500"
                >
                    {config.dashboardLabel}
                    <ExternalLink className="size-4" />
                </a>
                <a
                    href={`#gateway-settings-${provider}`}
                    className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-white/20 px-4 py-2 text-sm font-semibold text-white hover:bg-white/10"
                >
                    <KeyRound className="size-4" />
                    Save keys in KMJ
                    <ArrowRight className="size-4" />
                </a>
                <a
                    href={config.docs}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-white/20 px-4 py-2 text-sm font-semibold text-white hover:bg-white/10"
                >
                    Official provider docs
                    <ExternalLink className="size-4" />
                </a>
            </div>

            <form
                onSubmit={testConnection}
                className="mt-6 rounded-xl border border-white/10 bg-black/20 p-4"
                aria-label={`Test ${config.name} sandbox API connection`}
            >
                <p className="text-sm font-bold text-white">
                    Test stored sandbox credentials
                </p>
                <p className="mt-2 max-w-3xl text-xs leading-6 text-slate-300">
                    After saving test keys, this action creates a ₹1 TEST
                    order on the provider sandbox only. It does not charge a
                    card, capture money, confirm a subscription or grant a
                    license. An accepted test order does not mean checkout
                    and webhooks are production-ready.
                </p>
                {provider === 'cashfree' && (
                    <label className="mt-4 block max-w-sm space-y-2 text-xs font-semibold text-slate-200">
                        <span>
                            Your authorized Cashfree sandbox test phone
                        </span>
                        <input
                            type="tel"
                            inputMode="numeric"
                            autoComplete="off"
                            value={probe.data.test_phone}
                            maxLength={10}
                            onChange={(event) =>
                                probe.setData('test_phone', event.target.value)
                            }
                            placeholder="10-digit test phone"
                            className="w-full rounded-xl border border-white/20 bg-[#171c24] px-4 py-3 text-sm text-white"
                        />
                        <span className="block text-xs font-normal text-slate-400">
                            Used only to create your explicit sandbox test
                            order; may receive test-provider notifications.
                        </span>
                        {probe.errors.test_phone && (
                            <span className="block text-xs text-red-300" role="alert">
                                {probe.errors.test_phone}
                            </span>
                        )}
                    </label>
                )}
                <div className="mt-4 flex flex-wrap items-center gap-3">
                    <button
                        type="submit"
                        disabled={
                            !keysSaved ||
                            probe.processing ||
                            (provider === 'cashfree' &&
                                !/^[6-9][0-9]{9}$/.test(probe.data.test_phone))
                        }
                        className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-red-600 px-5 py-2 text-sm font-bold text-white hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                        <ShieldCheck className="size-4" />
                        {probe.processing ? 'Testing sandbox…' : 'Test Connection'}
                    </button>
                    {!keysSaved && (
                        <span className="text-xs text-amber-200">
                            Save sandbox API keys above before testing.
                        </span>
                    )}
                </div>
                {probe.errors.sandbox_probe && (
                    <p role="alert" className="mt-3 text-xs text-amber-200">
                        {probe.errors.sandbox_probe}
                    </p>
                )}
                {probe.recentlySuccessful && (
                    <p role="status" className="mt-3 text-xs text-emerald-300">
                        Provider accepted sandbox test order only. No payment
                        collected; full transaction verification still pending.
                    </p>
                )}
            </form>

            <div className="mt-6 grid gap-4 rounded-xl border border-amber-500/20 bg-amber-500/[0.06] p-4 text-xs leading-6 text-amber-100 sm:grid-cols-2">
                <p className="flex gap-2">
                    <LockKeyhole className="mt-1 size-4 shrink-0" />
                    Do not configure a public webhook URL before KMJ has
                    deployed and verified a dedicated provider-specific HTTPS
                    receiver. Never substitute an arbitrary URL.
                </p>
                <p className="flex gap-2">
                    <ShieldCheck className="mt-1 size-4 shrink-0" />
                    Live payment mode stays off even when every test key is
                    stored. API keys, merchant approval, and an actual paid
                    transaction are separate verifications.
                </p>
            </div>
        </section>
    );
}
