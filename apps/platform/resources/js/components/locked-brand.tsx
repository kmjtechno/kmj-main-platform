const lockedBrandSymbol =
    'data:image/webp;base64,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';

type LockedBrandProps = {
    compact?: boolean;
    className?: string;
};

export default function LockedBrand({
    compact = false,
    className = '',
}: LockedBrandProps) {
    return (
        <span className={'inline-flex min-w-0 items-center gap-3 ' + className}>
            <span
                className={
                    'relative shrink-0 overflow-hidden rounded-lg border border-white/10 bg-[#343a40] shadow-[0_0_24px_rgba(226,27,35,0.10)] ' +
                    (compact ? 'h-9 w-14' : 'h-12 w-[4.5rem]')
                }
            >
                <img
                    src={lockedBrandSymbol}
                    alt=""
                    aria-hidden="true"
                    className="h-full w-full object-cover object-center"
                />
            </span>
            <span className="min-w-0 leading-none">
                <span
                    className={
                        'block whitespace-nowrap font-black tracking-[0.08em] ' +
                        (compact ? 'text-[13px]' : 'text-base')
                    }
                >
                    <span className="text-[#e21b23]">KMJ</span>{' '}
                    <span className="text-white">TECHNO</span>
                </span>
                <span
                    className={
                        'mt-1 block whitespace-nowrap font-semibold tracking-[0.18em] text-white/38 uppercase ' +
                        (compact ? 'text-[7px]' : 'text-[8px]')
                    }
                >
                    Innovate <span className="text-[#e21b23]">|</span> Build{' '}
                    <span className="text-[#e21b23]">|</span> Scale
                </span>
            </span>
        </span>
    );
}
