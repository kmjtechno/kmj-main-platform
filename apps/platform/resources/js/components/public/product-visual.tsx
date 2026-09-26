type ProductVisualProps = {
    slug: string;
    name: string;
    kind?: string;
    compact?: boolean;
};

const generatedVisuals: Record<string, string> = {
    'kmj-cloudos': '/assets/products/kmj-cloudos.webp',
    'kmj-calibration-pro': '/assets/products/kmj-calibration.webp',
    'kmj-forge': '/assets/products/kmj-forge.webp',
    'kmj-connect': '/assets/products/kmj-connect.webp',
    'kmj-cloud-nexus': '/assets/products/kmj-cloud-nexus.webp',
    'kmj-agent': '/assets/products/kmj-agent.webp',
    'kmj-creative-studio': '/assets/products/kmj-creative-studio.webp',
    'kmj-cinema-platform': '/assets/products/kmj-cinema-platform.webp',
    'kmj-360-dome': '/assets/products/kmj-cinema-platform.webp',
    'kmj-cinema-player': '/assets/products/kmj-cinema-platform.webp',
    'kmj-licensing-hub': '/assets/products/kmj-licensing-hub.webp',
};

const palette: Record<string, [string, string]> = {
    'kmj-cloudos': ['#25b4ff', '#5f6fff'],
    'kmj-calibration-pro': ['#ff2d55', '#ff8a3d'],
    'kmj-forge': ['#a87cff', '#5f6fff'],
    'kmj-connect': ['#27d3a2', '#22a6f2'],
    'kmj-cloud-nexus': ['#ff3347', '#8b5cf6'],
    'kmj-agent': ['#f15b3a', '#ff2d55'],
    'kmj-creative-studio': ['#ff7a18', '#af4cff'],
    'kmj-cinema-platform': ['#f7c948', '#ff3347'],
};

function initials(name: string) {
    return name
        .replace(/^KMJ\s+/i, '')
        .split(/\s+/)
        .slice(0, 2)
        .map((part) => part[0])
        .join('')
        .toUpperCase();
}

export default function ProductVisual({
    slug,
    name,
    kind,
    compact = false,
}: ProductVisualProps) {
    const generatedVisual = generatedVisuals[slug];
    const [accent, accent2] = palette[slug] ?? ['#e21b23', '#6d28d9'];
    const isCloud = kind === 'cloudos' || slug === 'kmj-cloudos';

    if (generatedVisual) {
        return (
            <div
                className={
                    'relative isolate overflow-hidden border border-white/[0.08] bg-[#090c12] ' +
                    (compact
                        ? 'h-52 rounded-[1.35rem]'
                        : 'h-72 rounded-[1.75rem]')
                }
            >
                <img
                    src={generatedVisual}
                    alt={name + ' — KMJ TECHNO'}
                    loading={compact ? 'lazy' : 'eager'}
                    decoding="async"
                    className="h-full w-full object-cover"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-[#05070a]/45 via-transparent to-transparent" />
            </div>
        );
    }
    const isCalibration =
        kind === 'calibration' || slug === 'kmj-calibration-pro';

    return (
        <div
            className={
                'relative isolate overflow-hidden border border-white/[0.08] bg-[#090c12] ' +
                (compact ? 'h-52 rounded-[1.35rem]' : 'h-72 rounded-[1.75rem]')
            }
        >
            <div
                className="absolute inset-0 opacity-70"
                style={{
                    background: `radial-gradient(circle at 76% 18%, ${accent}30, transparent 32%), radial-gradient(circle at 12% 86%, ${accent2}24, transparent 34%), linear-gradient(145deg, #10141d, #07090e 72%)`,
                }}
            />
            <div
                className="absolute inset-0 opacity-[0.16]"
                style={{
                    backgroundImage:
                        'linear-gradient(rgba(255,255,255,.11) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.11) 1px, transparent 1px)',
                    backgroundSize: compact ? '22px 22px' : '30px 30px',
                    maskImage:
                        'linear-gradient(to bottom, black, transparent 82%)',
                }}
            />

            <div className="absolute top-4 left-4 flex items-center gap-2 rounded-full border border-white/[0.08] bg-black/35 px-3 py-1.5 backdrop-blur-xl">
                <span
                    className="h-1.5 w-1.5 rounded-full"
                    style={{ backgroundColor: accent }}
                />
                <span className="text-[9px] font-black tracking-[0.18em] text-white/58 uppercase">
                    KMJ TECHNO · Product visual
                </span>
            </div>

            {isCloud ? (
                <div className="absolute inset-x-5 top-14 bottom-5 grid grid-cols-[.76fr_1.24fr] gap-3">
                    <div className="rounded-2xl border border-white/[0.08] bg-black/25 p-3">
                        <div className="text-[8px] font-black tracking-[.16em] text-white/35 uppercase">
                            Infrastructure
                        </div>
                        <div className="mt-3 space-y-2">
                            {[72, 54, 84, 63].map((width, index) => (
                                <div
                                    key={width}
                                    className="rounded-lg border border-white/[0.06] bg-white/[0.035] p-2"
                                >
                                    <div className="flex items-center justify-between">
                                        <span className="text-[8px] font-bold text-white/52">
                                            NODE {index + 1}
                                        </span>
                                        <span
                                            className="h-1.5 w-1.5 rounded-full"
                                            style={{ backgroundColor: accent }}
                                        />
                                    </div>
                                    <div className="mt-2 h-1 rounded-full bg-white/[0.06]">
                                        <div
                                            className="h-full rounded-full"
                                            style={{
                                                width: `${width}%`,
                                                backgroundColor: accent,
                                            }}
                                        />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                    <div className="rounded-2xl border border-white/[0.08] bg-black/30 p-3">
                        <div className="flex items-center justify-between">
                            <div>
                                <div className="text-[8px] font-black tracking-[.16em] text-white/35 uppercase">
                                    Control plane
                                </div>
                                <div className="mt-1 text-sm font-black text-white/82">
                                    Service topology
                                </div>
                            </div>
                            <div className="rounded-lg border border-white/[0.07] px-2 py-1 text-[8px] font-bold text-white/42">
                                LIVE MAP
                            </div>
                        </div>
                        <svg
                            viewBox="0 0 260 128"
                            className="mt-3 h-[112px] w-full"
                        >
                            <defs>
                                <linearGradient
                                    id={`cloud-${slug}`}
                                    x1="0"
                                    x2="1"
                                >
                                    <stop stopColor={accent} />
                                    <stop offset="1" stopColor={accent2} />
                                </linearGradient>
                            </defs>
                            <path
                                d="M31 74 L86 35 L137 68 L194 28 L229 65"
                                fill="none"
                                stroke="rgba(255,255,255,.14)"
                                strokeWidth="2"
                            />
                            <path
                                d="M31 74 L86 35 L137 68 L194 28 L229 65"
                                fill="none"
                                stroke={`url(#cloud-${slug})`}
                                strokeWidth="2.5"
                                strokeDasharray="4 5"
                            />
                            {[
                                [31, 74],
                                [86, 35],
                                [137, 68],
                                [194, 28],
                                [229, 65],
                            ].map(([x, y], i) => (
                                <g key={i}>
                                    <circle
                                        cx={x}
                                        cy={y}
                                        r="10"
                                        fill="#0c1017"
                                        stroke={accent}
                                        strokeWidth="1.6"
                                    />
                                    <circle cx={x} cy={y} r="3" fill={accent} />
                                </g>
                            ))}
                        </svg>
                    </div>
                </div>
            ) : isCalibration ? (
                <div className="absolute inset-x-5 top-14 bottom-5">
                    <div className="relative h-full overflow-hidden rounded-2xl border border-white/[0.08] bg-black/30">
                        <div className="absolute inset-x-8 top-7 h-[72%] rounded-[48%_48%_18%_18%/72%_72%_28%_28%] border border-white/[0.08] bg-gradient-to-b from-white/[0.03] to-black/25">
                            <div
                                className="absolute inset-[12%] rounded-[48%_48%_22%_22%/72%_72%_28%_28%] opacity-80"
                                style={{
                                    background: `radial-gradient(circle at 50% 44%, ${accent}3d, transparent 32%), linear-gradient(90deg, transparent 48%, ${accent}66 49%, ${accent}66 51%, transparent 52%), linear-gradient(transparent 48%, ${accent2}55 49%, ${accent2}55 51%, transparent 52%)`,
                                }}
                            />
                        </div>
                        <div className="absolute right-4 bottom-4 left-4 grid grid-cols-4 gap-2">
                            {['SETUP', 'CAPTURE', 'SOLVE', 'VERIFY'].map(
                                (label, i) => (
                                    <div
                                        key={label}
                                        className="rounded-lg border border-white/[0.06] bg-[#0d1118]/90 px-2 py-2"
                                    >
                                        <div className="text-[7px] font-black tracking-[.12em] text-white/34">
                                            {label}
                                        </div>
                                        <div className="mt-2 h-1 rounded-full bg-white/[0.07]">
                                            <div
                                                className="h-full rounded-full"
                                                style={{
                                                    width:
                                                        i < 2
                                                            ? '100%'
                                                            : i === 2
                                                              ? '66%'
                                                              : '34%',
                                                    backgroundColor:
                                                        i < 2
                                                            ? accent
                                                            : 'rgba(255,255,255,.18)',
                                                }}
                                            />
                                        </div>
                                    </div>
                                ),
                            )}
                        </div>
                    </div>
                </div>
            ) : (
                <div className="absolute inset-x-5 top-14 bottom-5 grid grid-cols-[1.05fr_.95fr] gap-3">
                    <div className="relative overflow-hidden rounded-2xl border border-white/[0.08] bg-black/25 p-4">
                        <div className="text-[8px] font-black tracking-[.16em] text-white/34 uppercase">
                            System identity
                        </div>
                        <div className="mt-3 flex items-center gap-3">
                            <div
                                className="grid h-14 w-14 place-items-center rounded-2xl text-lg font-black text-white"
                                style={{
                                    background: `linear-gradient(145deg, ${accent}, ${accent2})`,
                                    boxShadow: `0 18px 40px ${accent}22`,
                                }}
                            >
                                {initials(name)}
                            </div>
                            <div>
                                <div className="text-sm font-black text-white/85">
                                    {name}
                                </div>
                                <div className="mt-1 text-[8px] font-bold tracking-[.12em] text-white/35 uppercase">
                                    KMJ product system
                                </div>
                            </div>
                        </div>
                        <div className="mt-5 space-y-2">
                            {[88, 64, 76].map((width) => (
                                <div
                                    key={width}
                                    className="h-2 rounded-full bg-white/[0.06]"
                                >
                                    <div
                                        className="h-full rounded-full"
                                        style={{
                                            width: `${width}%`,
                                            background: `linear-gradient(90deg, ${accent}aa, ${accent2}88)`,
                                        }}
                                    />
                                </div>
                            ))}
                        </div>
                    </div>
                    <div className="grid grid-rows-2 gap-3">
                        {[0, 1].map((index) => (
                            <div
                                key={index}
                                className="relative overflow-hidden rounded-2xl border border-white/[0.08] bg-black/25"
                            >
                                <div
                                    className="absolute -right-3 -bottom-4 h-24 w-24 rounded-full blur-2xl"
                                    style={{
                                        backgroundColor: index
                                            ? accent2 + '3a'
                                            : accent + '3a',
                                    }}
                                />
                                <div className="absolute inset-3 grid grid-cols-3 gap-2">
                                    {Array.from({ length: 6 }).map((_, i) => (
                                        <div
                                            key={i}
                                            className="rounded-lg border border-white/[0.06] bg-white/[0.035]"
                                        />
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
