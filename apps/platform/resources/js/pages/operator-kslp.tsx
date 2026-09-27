import { Head, router, useForm } from "@inertiajs/react";
import {
    KeyRound,
    ShieldCheck,
    Server,
    RefreshCw,
    Ban,
    Activity,
} from "lucide-react";

type License = {
    id: string;
    customer_id: string;
    product: string;
    plan: string;
    status: string;
    state: string;
    sequence: number;
    expires_at: string;
    grace_until: string | null;
    active_activations: number;
};
type Event = {
    id: number;
    license_id: string;
    action: string;
    actor_id: string;
    reason: string | null;
    correlation_id: string;
    created_at: string;
};
type Props = {
    metrics: {
        licenses: number;
        active: number;
        trials: number;
        activations: number;
        revoked: number;
        issuerSubscriptions: number;
    };
    licenses: License[];
    events: Event[];
};

export default function OperatorKslp({ metrics, licenses, events }: Props) {
    const issue = useForm({
        customer_id: "",
        plan: "trial",
        reason: "Commercial license issued by platform owner",
    });
    const cards = [
        ["Licenses", metrics.licenses],
        ["Active", metrics.active],
        ["Trials", metrics.trials],
        ["Activations", metrics.activations],
        ["Revoked", metrics.revoked],
        ["Issuer subscriptions", metrics.issuerSubscriptions],
    ] as const;
    const action = (
        id: string,
        a: string,
        extra: Record<string, unknown> = {},
    ) =>
        router.post(
            `/operator/kslp/licenses/${id}/action`,
            { action: a, reason: `Owner approved ${a}`, ...extra },
            { preserveScroll: true },
        );
    return (
        <>
            <Head title="KSLP License Control Plane" />
            <div className="flex h-full flex-1 flex-col gap-6 overflow-x-auto p-4 sm:p-6">
                <section className="rounded-2xl border bg-card p-6">
                    <div className="flex gap-4">
                        <span className="grid h-11 w-11 place-items-center rounded-xl bg-red-500/10 text-red-500">
                            <ShieldCheck className="h-5 w-5" />
                        </span>
                        <div>
                            <div className="text-xs font-bold uppercase tracking-wider text-red-500">
                                KMJ Main Platform authority
                            </div>
                            <h1 className="mt-1 text-2xl font-black">
                                KSLP Commercial License Control Plane
                            </h1>
                            <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
                                CloudOS is a licensed product. Main Platform
                                remains the commercial authority for issue,
                                lifecycle, server activations and audit
                                evidence.
                            </p>
                        </div>
                    </div>
                </section>
                <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                    {cards.map(([l, v]) => (
                        <div key={l} className="rounded-xl border bg-card p-4">
                            <div className="text-xs text-muted-foreground">
                                {l}
                            </div>
                            <div className="mt-2 text-2xl font-black">{v}</div>
                        </div>
                    ))}
                </section>
                <section className="rounded-2xl border bg-card p-5">
                    <h2 className="font-bold">Issue KMJ CloudOS license</h2>
                    <form
                        className="mt-4 grid gap-3 lg:grid-cols-[1.2fr_.7fr_1.5fr_auto]"
                        onSubmit={(e) => {
                            e.preventDefault();
                            issue.post("/operator/kslp/licenses", {
                                preserveScroll: true,
                                onSuccess: () => issue.reset("customer_id"),
                            });
                        }}
                    >
                        <input
                            className="h-10 rounded-lg border bg-background px-3 text-sm"
                            placeholder="Customer / organization ID"
                            value={issue.data.customer_id}
                            onChange={(e) =>
                                issue.setData("customer_id", e.target.value)
                            }
                            required
                        />
                        <select
                            className="h-10 rounded-lg border bg-background px-3 text-sm"
                            value={issue.data.plan}
                            onChange={(e) =>
                                issue.setData("plan", e.target.value)
                            }
                        >
                            {[
                                "trial",
                                "professional",
                                "business",
                                "enterprise",
                                "custom_oem",
                            ].map((p) => (
                                <option key={p} value={p}>
                                    {p}
                                </option>
                            ))}
                        </select>
                        <input
                            className="h-10 rounded-lg border bg-background px-3 text-sm"
                            value={issue.data.reason}
                            onChange={(e) =>
                                issue.setData("reason", e.target.value)
                            }
                            required
                        />
                        <button
                            disabled={issue.processing}
                            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-red-600 px-4 text-xs font-bold text-white"
                        >
                            <KeyRound className="h-4 w-4" />
                            Issue
                        </button>
                    </form>
                    {Object.keys(issue.errors).length > 0 && (
                        <p className="mt-2 text-xs text-red-500">
                            {Object.values(issue.errors)[0]}
                        </p>
                    )}
                </section>
                <section className="rounded-2xl border bg-card p-5">
                    <div className="flex items-center justify-between">
                        <div>
                            <h2 className="font-bold">Commercial licenses</h2>
                            <p className="mt-1 text-xs text-muted-foreground">
                                Lifecycle mutations require platform-owner
                                access and recent password confirmation.
                            </p>
                        </div>
                        <Server className="h-5 w-5 text-red-500" />
                    </div>
                    <div className="mt-4 overflow-x-auto">
                        <table className="w-full min-w-[980px] text-left text-xs">
                            <thead className="text-muted-foreground">
                                <tr>
                                    {[
                                        "License / customer",
                                        "Product / plan",
                                        "State",
                                        "Sequence",
                                        "Expiry",
                                        "Activations",
                                        "Actions",
                                    ].map((x) => (
                                        <th key={x} className="border-b p-3">
                                            {x}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {licenses.map((l) => (
                                    <tr
                                        key={l.id}
                                        className="border-b last:border-0"
                                    >
                                        <td className="p-3">
                                            <div className="font-mono font-semibold">
                                                {l.id}
                                            </div>
                                            <div className="mt-1 text-muted-foreground">
                                                {l.customer_id}
                                            </div>
                                        </td>
                                        <td className="p-3">
                                            <b>{l.product}</b>
                                            <div>{l.plan}</div>
                                        </td>
                                        <td className="p-3 font-bold">
                                            {l.state}
                                        </td>
                                        <td className="p-3">{l.sequence}</td>
                                        <td className="p-3">{l.expires_at}</td>
                                        <td className="p-3">
                                            {l.active_activations}
                                        </td>
                                        <td className="p-3">
                                            <div className="flex flex-wrap gap-2">
                                                {l.state === "REVOKED" ? (
                                                    <button
                                                        onClick={() =>
                                                            action(
                                                                l.id,
                                                                "reactivate",
                                                            )
                                                        }
                                                        className="rounded border px-2 py-1"
                                                    >
                                                        <RefreshCw className="inline h-3 w-3" />{" "}
                                                        Reactivate
                                                    </button>
                                                ) : (
                                                    <button
                                                        onClick={() =>
                                                            action(
                                                                l.id,
                                                                "revoke",
                                                            )
                                                        }
                                                        className="rounded border px-2 py-1"
                                                    >
                                                        <Ban className="inline h-3 w-3" />{" "}
                                                        Revoke
                                                    </button>
                                                )}
                                                <button
                                                    onClick={() =>
                                                        action(l.id, "renew", {
                                                            days: 365,
                                                        })
                                                    }
                                                    className="rounded border px-2 py-1"
                                                >
                                                    Renew 1y
                                                </button>
                                                <select
                                                    aria-label="Change plan"
                                                    value={
                                                        l.plan === "trial"
                                                            ? "professional"
                                                            : l.plan
                                                    }
                                                    onChange={(e) =>
                                                        action(
                                                            l.id,
                                                            "change_plan",
                                                            {
                                                                plan: e.target
                                                                    .value,
                                                            },
                                                        )
                                                    }
                                                    className="rounded border bg-background px-2 py-1"
                                                >
                                                    {[
                                                        "professional",
                                                        "business",
                                                        "enterprise",
                                                        "custom_oem",
                                                    ].map((p) => (
                                                        <option key={p}>
                                                            {p}
                                                        </option>
                                                    ))}
                                                </select>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </section>
                <section className="rounded-2xl border bg-card p-5">
                    <div className="flex items-center gap-2">
                        <Activity className="h-4 w-4 text-red-500" />
                        <h2 className="font-bold">
                            Immutable lifecycle audit trail
                        </h2>
                    </div>
                    <div className="mt-4 grid gap-2">
                        {events.map((e) => (
                            <div
                                key={e.id}
                                className="grid gap-1 rounded-xl border p-3 text-xs md:grid-cols-[1fr_.8fr_1fr_1.5fr]"
                            >
                                <b>{e.action}</b>
                                <span>{e.created_at}</span>
                                <span className="font-mono">
                                    {e.license_id}
                                </span>
                                <span className="text-muted-foreground">
                                    {e.reason ?? "—"}
                                </span>
                            </div>
                        ))}
                    </div>
                </section>
            </div>
        </>
    );
}
