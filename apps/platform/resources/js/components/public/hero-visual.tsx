export default function HeroVisual() {
    return (
        <div className="relative min-h-[420px] overflow-hidden rounded-[2rem] border border-white/[0.09] bg-[#0a0d13] shadow-[0_40px_120px_rgba(0,0,0,.45)]">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_72%_18%,rgba(226,27,35,.28),transparent_28%),radial-gradient(circle_at_24%_78%,rgba(99,102,241,.18),transparent_34%),linear-gradient(145deg,#111722,#06080c_72%)]" />
            <div className="absolute inset-0 [background-image:linear-gradient(rgba(255,255,255,.12)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,.12)_1px,transparent_1px)] [mask-image:linear-gradient(to_bottom,black,transparent_90%)] [background-size:32px_32px] opacity-[.16]" />

            <div className="absolute top-5 right-5 left-5 flex items-center justify-between">
                <div className="flex items-center gap-2 rounded-full border border-white/[0.08] bg-black/35 px-3 py-1.5 backdrop-blur-xl">
                    <span className="h-1.5 w-1.5 rounded-full bg-[#e21b23]" />
                    <span className="text-[9px] font-black tracking-[.18em] text-white/58 uppercase">
                        KMJ TECHNO · Unified platform
                    </span>
                </div>
                <div className="rounded-full border border-emerald-300/15 bg-emerald-300/[0.05] px-3 py-1.5 text-[9px] font-black tracking-[.14em] text-emerald-200/70 uppercase">
                    Governed systems
                </div>
            </div>

            <div className="absolute inset-x-5 top-20 bottom-5 grid grid-cols-[.72fr_1.28fr] gap-4">
                <div className="space-y-3">
                    {['Cloud', 'Calibration', 'Engineering', 'Access'].map(
                        (label, i) => (
                            <div
                                key={label}
                                className="rounded-2xl border border-white/[0.08] bg-black/30 p-4 backdrop-blur"
                            >
                                <div className="flex items-center justify-between">
                                    <span className="text-[10px] font-black tracking-[.13em] text-white/52 uppercase">
                                        {label}
                                    </span>
                                    <span
                                        className={`h-2 w-2 rounded-full ${i === 0 ? 'bg-[#31b8ff]' : i === 1 ? 'bg-[#ff3b50]' : i === 2 ? 'bg-[#a87cff]' : 'bg-[#27d3a2]'}`}
                                    />
                                </div>
                                <div className="mt-3 h-1.5 rounded-full bg-white/[0.06]">
                                    <div
                                        className="h-full rounded-full bg-gradient-to-r from-[#e21b23] to-[#7c3aed]"
                                        style={{
                                            width: `${[84, 68, 76, 62][i]}%`,
                                        }}
                                    />
                                </div>
                            </div>
                        ),
                    )}
                </div>

                <div className="relative overflow-hidden rounded-[1.6rem] border border-white/[0.08] bg-black/30 p-5 backdrop-blur">
                    <div className="flex items-start justify-between">
                        <div>
                            <div className="text-[9px] font-black tracking-[.16em] text-white/32 uppercase">
                                Product ecosystem
                            </div>
                            <div className="mt-2 text-xl font-black tracking-[-.035em] text-white/90">
                                One control surface.
                                <span className="block text-white/38">
                                    Multiple independent systems.
                                </span>
                            </div>
                        </div>
                        <div className="grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-[#e21b23] to-[#721019] text-sm font-black">
                            KMJ
                        </div>
                    </div>

                    <svg
                        viewBox="0 0 420 210"
                        className="absolute inset-x-5 bottom-5 h-[205px] w-[calc(100%-2.5rem)]"
                    >
                        <defs>
                            <linearGradient id="hero-line" x1="0" x2="1">
                                <stop stopColor="#e21b23" />
                                <stop offset=".55" stopColor="#8b5cf6" />
                                <stop offset="1" stopColor="#31b8ff" />
                            </linearGradient>
                            <radialGradient id="hero-node">
                                <stop stopColor="#ffffff" stopOpacity=".95" />
                                <stop
                                    offset="1"
                                    stopColor="#e21b23"
                                    stopOpacity=".2"
                                />
                            </radialGradient>
                        </defs>
                        <path
                            d="M34 126 C95 60 120 152 179 86 S278 33 385 112"
                            fill="none"
                            stroke="rgba(255,255,255,.12)"
                            strokeWidth="12"
                        />
                        <path
                            d="M34 126 C95 60 120 152 179 86 S278 33 385 112"
                            fill="none"
                            stroke="url(#hero-line)"
                            strokeWidth="2.5"
                            strokeDasharray="7 8"
                        />
                        {[
                            [34, 126],
                            [108, 88],
                            [179, 86],
                            [265, 55],
                            [385, 112],
                        ].map(([x, y], i) => (
                            <g key={i}>
                                <circle
                                    cx={x}
                                    cy={y}
                                    r={i === 2 ? 17 : 13}
                                    fill="#0a0d13"
                                    stroke={
                                        i === 2
                                            ? '#e21b23'
                                            : 'rgba(255,255,255,.25)'
                                    }
                                    strokeWidth="2"
                                />
                                <circle
                                    cx={x}
                                    cy={y}
                                    r="4"
                                    fill="url(#hero-node)"
                                />
                            </g>
                        ))}
                    </svg>
                </div>
            </div>
        </div>
    );
}
