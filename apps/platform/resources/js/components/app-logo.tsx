import LockedBrand from '@/components/locked-brand';

export default function AppLogo() {
    return (
        <>
            <div className="border-sidebar-border flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-lg border bg-[#080a0e]">
                <img
                    src="/assets/brand/kmj-app-icon.png"
                    alt=""
                    aria-hidden="true"
                    className="h-full w-full object-cover"
                />
            </div>
            <LockedBrand compact className="ml-1 min-w-0 overflow-hidden" />
        </>
    );
}
