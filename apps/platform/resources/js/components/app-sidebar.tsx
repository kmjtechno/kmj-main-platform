import { Link, usePage } from '@inertiajs/react';
import {
    Activity,
    Crown,
    CreditCard,
    Code2,
    FlaskConical,
    KeyRound,
    LayoutGrid,
    PackageOpen,
    ShieldCheck,
    ShoppingCart,
} from 'lucide-react';
import AppLogo from '@/components/app-logo';
import { NavFooter } from '@/components/nav-footer';
import { NavMain } from '@/components/nav-main';
import { NavUser } from '@/components/nav-user';
import {
    Sidebar,
    SidebarContent,
    SidebarFooter,
    SidebarHeader,
    SidebarMenu,
    SidebarMenuButton,
    SidebarMenuItem,
} from '@/components/ui/sidebar';
import { dashboard } from '@/routes';
import { edit as securitySettings } from '@/routes/security';
import type { NavItem } from '@/types';

const baseNavItems: NavItem[] = [
    {
        title: 'Dashboard',
        href: dashboard(),
        icon: LayoutGrid,
    },
    {
        title: 'Purchase Center',
        href: '/purchase',
        icon: ShoppingCart,
    },
    {
        title: 'Developer Apps & Keys',
        href: '/developer/apps',
        icon: Code2,
    },
    {
        title: 'Sandbox Token Lab',
        href: '/sandbox-licenses',
        icon: FlaskConical,
    },
    {
        title: 'Security',
        href: securitySettings(),
        icon: ShieldCheck,
    },
];

const footerNavItems: NavItem[] = [
    {
        title: 'KMJ Products',
        href: '/products',
        icon: PackageOpen,
    },
    {
        title: 'Trust Center',
        href: '/trust',
        icon: ShieldCheck,
    },
];

export function AppSidebar() {
    const operator = usePage().props.operator as
        | { enabled?: boolean }
        | undefined;
    const ownerNavItems: NavItem[] = operator?.enabled
        ? [
              { title: 'Overview', href: '/operator', icon: Crown },
              {
                  title: 'Product Management',
                  href: '/operator/products',
                  icon: PackageOpen,
              },
              {
                  title: 'Licensing Center',
                  href: '/operator/kslp',
                  icon: KeyRound,
              },
              {
                  title: 'Customers & Organizations',
                  href: '/operator/directory',
                  icon: Crown,
              },
              {
                  title: 'Payment Gateways',
                  href: '/operator/payments',
                  icon: CreditCard,
              },
              {
                  title: 'Operations',
                  href: '/operator/ops',
                  icon: Activity,
              },
          ]
        : [];

    return (
        <Sidebar collapsible="icon" variant="inset" className="kmj-premium-sidebar">
            <SidebarHeader>
                <SidebarMenu>
                    <SidebarMenuItem>
                        <SidebarMenuButton size="lg" asChild>
                            <Link href={dashboard()} prefetch>
                                <AppLogo />
                            </Link>
                        </SidebarMenuButton>
                    </SidebarMenuItem>
                </SidebarMenu>
            </SidebarHeader>

            <SidebarContent>
                <NavMain items={baseNavItems} label="My workspace" />
                {ownerNavItems.length > 0 && (
                    <NavMain items={ownerNavItems} label="Super Admin" />
                )}
            </SidebarContent>

            <SidebarFooter>
                <NavFooter items={footerNavItems} className="mt-auto" />
                <NavUser />
            </SidebarFooter>
        </Sidebar>
    );
}
