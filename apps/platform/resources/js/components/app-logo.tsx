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
            <div className="ml-1 min-w-0 flex-1 text-left leading-none">
                <div className="truncate text-[13px] font-black tracking-[0.07em]">
                    <span className="text-red-600">KMJ</span> TECHNO
                </div>
                <div className="text-muted-foreground mt-1 truncate text-[7px] font-semibold tracking-[0.16em] uppercase">
                    Innovate | Build | Scale
                </div>
            </div>
        </>
    );
}
