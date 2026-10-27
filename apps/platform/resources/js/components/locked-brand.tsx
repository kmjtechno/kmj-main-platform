type LockedBrandProps = { compact?: boolean; className?: string };

export default function LockedBrand({
    compact = false,
    className = '',
}: LockedBrandProps) {
    return (
        <span
            className={
                'kmj-brand inline-flex min-w-0 items-center ' + className
            }
        >
            <picture className="block w-full">
                <source
                    srcSet="/assets/brand/kmj-logo-horizontal-transparent.svg"
                    type="image/svg+xml"
                />
                <img
                    src="/assets/brand/kmj-logo-horizontal.webp"
                    width="910"
                    height="220"
                    alt="KMJ TECHNO — INNOVATE | BUILD | SCALE"
                    decoding="async"
                    className={
                        'kmj-brand-image block w-auto object-contain ' +
                        (compact ? 'h-9 sm:h-10' : 'h-12 sm:h-14')
                    }
                />
            </picture>
        </span>
    );
}
