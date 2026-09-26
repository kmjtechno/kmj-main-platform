type LockedBrandProps = {
    compact?: boolean;
    className?: string;
};

export default function LockedBrand({
    compact = false,
    className = '',
}: LockedBrandProps) {
    return (
        <span className={'inline-flex min-w-0 items-center ' + className}>
            <img
                src="/assets/brand/kmj-logo-horizontal.webp"
                alt="KMJ TECHNO — INNOVATE | BUILD | SCALE"
                decoding="async"
                className={
                    'block w-auto object-contain ' +
                    (compact ? 'h-9 sm:h-10' : 'h-12 sm:h-14')
                }
            />
        </span>
    );
}
