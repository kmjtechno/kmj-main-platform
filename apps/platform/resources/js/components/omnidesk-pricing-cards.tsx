import { Link } from '@inertiajs/react';
import { BadgeCheck, ShieldCheck } from 'lucide-react';
import { useState } from 'react';

export type OmniDeskOffer = {
    code: string;
    name: string;
    amount_minor: number | null;
    currency: string | null;
    billing_interval: string | null;
    trial_days: number;
    licensed_users: number;
    managed_devices: number;
    concurrent_sessions: number;
    unattended_devices: number;
    relay_bytes_monthly: number;
    relay_policy: string;
    commercial_use: boolean;
    available: boolean;
};

type Props = {
    offers: OmniDeskOffer[];
    trialEnabled: boolean;
    paidCheckoutEnabled: boolean;
};

function offerPrice(offer: OmniDeskOffer): string {
    if (offer.amount_minor === null) return 'Free';
    if (offer.currency !== 'INR') return 'Quote only';
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        maximumFractionDigits: 0,
    }).format(offer.amount_minor / 100);
}

const ORDER = [
    'omnidesk.personal_free',
    'omnidesk.trial',
    'omnidesk.professional',
    'omnidesk.business',
    'omnidesk.enterprise',
] as const;

export default function OmniDeskPricingCards({
    offers,
    trialEnabled,
    paidCheckoutEnabled,
}: Props) {
    const [billing, setBilling] = useState<'monthly' | 'yearly'>('monthly');
    const cards = ORDER.map((key) => {
        const fullCode =
            key === 'omnidesk.professional' ||
            key === 'omnidesk.business' ||
            key === 'omnidesk.enterprise'
                ? `${key}.${billing}`
                : key;

        return offers.find((offer) => offer.code === fullCode);
    }).filter((offer): offer is OmniDeskOffer => offer !== undefined);

    return (
        <section
            id="omnidesk-offers"
            aria-labelledby="omnidesk-pricing-heading"
            className="bg-card scroll-mt-6 rounded-2xl border p-5 sm:p-6"
        >
            <div className="flex flex-wrap items-start justify-between gap-5">
                <div className="max-w-2xl">
                    <p className="mb-2 text-xs font-bold tracking-[0.18em] text-red-500 uppercase">
                        KMJ OmniDesk · transparent India launch offers
                    </p>
                    <h2
                        id="omnidesk-pricing-heading"
                        className="text-2xl font-black tracking-tight"
                    >
                        Start free. Upgrade when your work grows.
                    </h2>
                    <p className="text-muted-foreground mt-2 text-xs leading-6">
                        Personal use without a card, a one-time 14-day business
                        trial, and affordable team plans. Direct connections are
                        prioritized to manage infrastructure cost. These are
                        planned offers, not a claim that remote control or
                        checkout is live.
                    </p>
                </div>
                <div
                    role="group"
                    aria-label="Compare subscription billing"
                    className="bg-muted inline-flex rounded-xl p-1"
                >
                    <button
                        type="button"
                        aria-pressed={billing === 'monthly'}
                        onClick={() => setBilling('monthly')}
                        className={`min-h-10 rounded-lg px-4 text-xs font-bold ${billing === 'monthly' ? 'bg-background shadow-sm' : 'text-muted-foreground'}`}
                    >
                        Monthly
                    </button>
                    <button
                        type="button"
                        aria-pressed={billing === 'yearly'}
                        onClick={() => setBilling('yearly')}
                        className={`min-h-10 rounded-lg px-4 text-xs font-bold ${billing === 'yearly' ? 'bg-background shadow-sm' : 'text-muted-foreground'}`}
                    >
                        Yearly · 2 months free
                    </button>
                </div>
            </div>
            <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                {cards.map((offer) => {
                    const isTrial = offer.code === 'omnidesk.trial';
                    const isFree = offer.code === 'omnidesk.personal_free';
                    const isPaid = !isTrial && !isFree;
                    const ready =
                        offer.available &&
                        (isTrial
                            ? trialEnabled
                            : isPaid
                              ? paidCheckoutEnabled
                              : false);
                    const label = isTrial
                        ? '14 days · no payment card'
                        : isFree
                          ? 'Personal, non-commercial'
                          : offer.billing_interval === 'yearly'
                            ? 'Billed yearly upfront'
                            : 'Billed monthly';
                    return (
                        <article
                            key={offer.code}
                            className="border-border flex flex-col rounded-2xl border p-4"
                        >
                            <h3 className="text-sm font-extrabold">
                                {offer.name.replace(/ (Monthly|Yearly)$/, '')}
                            </h3>
                            <p className="text-muted-foreground mt-1 text-[11px]">
                                {label}
                            </p>
                            <p className="mt-4 text-2xl font-black tabular-nums">
                                {offerPrice(offer)}
                                {isPaid &&
                                    offer.billing_interval === 'yearly' && (
                                        <span className="text-muted-foreground ml-1 text-xs font-medium">
                                            /year
                                        </span>
                                    )}
                                {isPaid &&
                                    offer.billing_interval === 'monthly' && (
                                        <span className="text-muted-foreground ml-1 text-xs font-medium">
                                            /month
                                        </span>
                                    )}
                            </p>
                            {isPaid &&
                                billing === 'yearly' &&
                                offer.amount_minor !== null && (
                                    <p className="mt-1 text-xs font-semibold text-emerald-600">
                                        ≈{' '}
                                        {offerPrice({
                                            ...offer,
                                            amount_minor: Math.round(
                                                offer.amount_minor / 12,
                                            ),
                                        })}
                                        /month equivalent
                                    </p>
                                )}
                            <div className="text-muted-foreground mt-4 space-y-1.5 text-xs">
                                <p>
                                    {offer.licensed_users} users ·{' '}
                                    {offer.managed_devices} managed devices
                                </p>
                                <p>
                                    {offer.concurrent_sessions} concurrent
                                    session(s)
                                </p>
                                <p>
                                    {offer.unattended_devices} unattended
                                    devices
                                </p>
                                <p>
                                    {offer.relay_bytes_monthly === 0
                                        ? 'Direct connection only'
                                        : `${Math.round(offer.relay_bytes_monthly / 1073741824)} GiB monthly relay allowance`}
                                </p>
                                <p>
                                    {offer.commercial_use
                                        ? 'Commercial use included'
                                        : 'Non-commercial use only'}
                                </p>
                            </div>
                            <div className="mt-auto pt-5">
                                {isTrial && ready ? (
                                    <Link
                                        href="/licensing"
                                        className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-red-600 px-3 text-xs font-bold text-white hover:bg-red-500"
                                    >
                                        <BadgeCheck
                                            className="size-4"
                                            aria-hidden="true"
                                        />
                                        Start no-card trial
                                    </Link>
                                ) : (
                                    <p
                                        className="bg-muted flex min-h-11 items-center justify-center rounded-xl px-3 text-center text-xs font-semibold"
                                        aria-label={
                                            ready
                                                ? 'Checkout reviewed separately'
                                                : 'Not available yet'
                                        }
                                    >
                                        <ShieldCheck
                                            className="mr-1.5 size-4"
                                            aria-hidden="true"
                                        />
                                        {ready
                                            ? 'Checkout approval required'
                                            : 'Coming after release checks'}
                                    </p>
                                )}
                            </div>
                        </article>
                    );
                })}
            </div>
            <p className="text-muted-foreground mt-4 text-xs leading-5">
                Prices shown before applicable taxes. Yearly plans charge a full
                annual amount in advance; no hidden monthly collection. Trial
                does not auto-renew or charge without a separate authorized
                purchase. Relay traffic, devices and sessions are capped by
                plan. Production payment and signing are subject to merchant
                verification and KMJ release approval.
            </p>
        </section>
    );
}
