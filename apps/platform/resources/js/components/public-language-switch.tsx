import { Link, usePage } from '@inertiajs/react';

export default function PublicLanguageSwitch({
    className = '',
}: {
    className?: string;
}) {
    const { localization } = usePage().props;

    return (
        <Link
            href={localization.switch_url}
            preserveScroll
            aria-label={`Switch language to ${localization.switch_label}`}
            className={className}
        >
            {localization.switch_label}
        </Link>
    );
}
