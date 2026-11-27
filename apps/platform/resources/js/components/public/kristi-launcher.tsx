import { MessageCircle, X } from 'lucide-react';

type KristiLauncherProps = {
    label: string;
    open?: boolean;
    accessibleName?: string;
    onClick: () => void;
};

/** Round Kristi avatar that opens or closes the product guide. */
export default function KristiLauncher({
    label,
    open = false,
    accessibleName,
    onClick,
}: KristiLauncherProps) {
    return (
        <button
            type="button"
            className="kmj-kristi-launcher"
            aria-expanded={open}
            aria-label={accessibleName ?? label}
            onClick={onClick}
        >
            <span aria-hidden="true" className="kmj-kristi-label">
                {label}
            </span>
            <span aria-hidden="true" className="kmj-kristi-face">
                <img
                    src="/assets/locked/kristi-public.webp"
                    alt=""
                    width="64"
                    height="96"
                />
                <span className="kmj-kristi-badge">
                    {open ? <X size={13} /> : <MessageCircle size={13} />}
                </span>
            </span>
        </button>
    );
}
