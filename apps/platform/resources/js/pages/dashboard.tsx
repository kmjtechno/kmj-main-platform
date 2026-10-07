import { Head } from '@inertiajs/react';
import CustomerControlCenter from '@/components/customer-control-center';
import { dashboard } from '@/routes';

type CodeBridgeService = {
    kind: 'codebridge';
    plan: string | null;
    managed_devices: number;
    pending_pairings: number;
    license_expires_at: string | null;
    oauth_ready: boolean;
};

type Entitlement = {
    id: string;
    product_slug: string;
    product_name: string;
    capability: string;
    status: string;
    release: {
        version: string;
        download_url: string;
    } | null;
    service?: CodeBridgeService | null;
};

type DashboardProps = {
    organizations: Array<{
        id: string;
        name: string;
        role: string;
        entitlements: Entitlement[];
    }>;
    catalog: Array<{
        slug: string;
        name: string;
        summary: string;
        category: string;
        lifecycle_label: string;
        purchase_enabled: boolean;
        image_path?: string | null;
    }>;
    hasPasskey: boolean;
};

export default function Dashboard({
    organizations,
    catalog,
    hasPasskey,
}: DashboardProps) {
    return (
        <>
            <Head title="Customer Control Center — KMJ TECHNO" />
            <CustomerControlCenter
                organizations={organizations}
                catalog={catalog}
                hasPasskey={hasPasskey}
            />
        </>
    );
}

Dashboard.layout = {
    breadcrumbs: [
        {
            title: 'My Services',
            href: dashboard(),
        },
    ],
};
