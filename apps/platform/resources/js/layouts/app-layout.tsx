import { usePage } from '@inertiajs/react';
import OwnerModuleShell from '@/layouts/owner-module-shell';
import AppLayoutTemplate from '@/layouts/app/app-sidebar-layout';
import type { BreadcrumbItem } from '@/types';

export default function AppLayout({
    breadcrumbs = [],
    children,
}: {
    breadcrumbs?: BreadcrumbItem[];
    children: React.ReactNode;
}) {
    const { operator } = usePage().props;
    const isOwner =
        typeof operator === 'object' &&
        operator !== null &&
        'enabled' in operator &&
        operator.enabled === true;

    if (isOwner) {
        return <OwnerModuleShell>{children}</OwnerModuleShell>;
    }

    return (
        <AppLayoutTemplate breadcrumbs={breadcrumbs}>
            {children}
        </AppLayoutTemplate>
    );
}
