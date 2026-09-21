import { useMemo, useState } from 'react';
import { ArrowRight, CheckCircle2, Circle, RotateCcw, ServerCog } from 'lucide-react';

type Step = {
    key: string;
    label: string;
    detail: string;
};

export default function CloudOSDemo({ steps }: { steps: Step[] }) {
    const [active, setActive] = useState(0);
    const current = steps[active];
    const progress = useMemo(
        () => Math.round(((active + 1) / Math.max(steps.length, 1)) * 100),
        [active, steps.length],
    );

    return (
        <div className="overflow-hidden rounded-[1.75rem] border border-white/[0.09] bg-[#080a0d]">
            <div className="grid lg:grid-cols-[.72fr_1.28fr]">
                <div className="border-b border-white/[0.07] p-6 lg:border-r lg:border-b-0 lg:p-8">
                    <div className="flex items-center justify-between">
                        <div>
                            <div className="text-[10px] font-bold tracking-[0.16em] text-[#ff6970] uppercase">
                                Simulation
                            </div>
                            <div className="mt-1 text-lg font-black">CloudOS workflow</div>
                        </div>
                        <div className="text-sm font-bold text-white/35">{progress}%</div>
                    </div>

                    <div className="mt-8 space-y-2">
                        {steps.map((step, index) => {
                            const done = index < active;
                            const selected = index === active;

                            return (
                                <button
                                    key={step.key}
                                    type="button"
                                    onClick={() => setActive(index)}
                                    className={
                                        selected
                                            ? 'flex w-full items-center gap-3 rounded-xl border border-[#e21b23]/35 bg-[#e21b23]/10 px-4 py-3 text-left transition'
                                            : 'flex w-full items-center gap-3 rounded-xl border border-white/[0.06] bg-white/[0.018] px-4 py-3 text-left transition hover:bg-white/[0.04]'
                                    }
                                >
                                    {done ? (
                                        <CheckCircle2 className="h-4 w-4 text-emerald-300" />
                                    ) : (
                                        <Circle
                                            className={
                                                selected
                                                    ? 'h-4 w-4 text-[#ef3941]'
                                                    : 'h-4 w-4 text-white/20'
                                            }
                                        />
                                    )}
                                    <span className="text-sm font-semibold">{step.label}</span>
                                </button>
                            );
                        })}
                    </div>
                </div>

                <div className="relative min-h-[430px] p-6 sm:p-8">
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_20%,rgba(226,27,35,0.12),transparent_34%)]" />
                    <div className="relative flex h-full flex-col">
                        <div className="grid flex-1 place-items-center rounded-2xl border border-white/[0.075] bg-black/20 p-5">
                            <div className="w-full max-w-2xl">
                                <div className="grid grid-cols-3 gap-3">
                                    {['Control', 'Worker', 'Service'].map((label, index) => (
                                        <div
                                            key={label}
                                            className="rounded-2xl border border-white/[0.07] bg-white/[0.025] p-4"
                                        >
                                            <ServerCog
                                                className={
                                                    index <= active % 3
                                                        ? 'h-5 w-5 text-[#ef3941]'
                                                        : 'h-5 w-5 text-white/20'
                                                }
                                            />
                                            <div className="mt-8 text-xs font-semibold text-white/60">
                                                {label}
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                <div className="mt-5 rounded-2xl border border-white/[0.08] bg-[#090b0f]/95 p-5">
                                    <div className="text-xs font-bold tracking-[0.14em] text-white/30 uppercase">
                                        Step {active + 1} of {steps.length}
                                    </div>
                                    <div className="mt-2 text-2xl font-black">{current.label}</div>
                                    <p className="mt-3 text-sm leading-6 text-white/48">
                                        {current.detail}
                                    </p>
                                    <div className="mt-4 text-xs leading-5 text-amber-100/55">
                                        Seeded browser simulation only — no live service, worker or
                                        infrastructure is controlled from this demo.
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="mt-5 flex items-center justify-between gap-4">
                            <button
                                type="button"
                                onClick={() => setActive(0)}
                                className="inline-flex h-10 items-center gap-2 rounded-lg border border-white/10 px-4 text-sm font-semibold text-white/50 transition hover:text-white"
                            >
                                <RotateCcw className="h-4 w-4" />
                                Reset
                            </button>
                            <button
                                type="button"
                                onClick={() =>
                                    setActive((value) => Math.min(value + 1, steps.length - 1))
                                }
                                disabled={active === steps.length - 1}
                                className="inline-flex h-10 items-center gap-2 rounded-lg bg-[#e21b23] px-4 text-sm font-bold transition hover:bg-[#f1252e] disabled:cursor-not-allowed disabled:opacity-35"
                            >
                                Next step
                                <ArrowRight className="h-4 w-4" />
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
