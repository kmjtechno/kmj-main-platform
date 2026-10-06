import { Link, usePage } from '@inertiajs/react';
import {
    Activity,
    Crown,
    KeyRound,
    LayoutGrid,
    PackageOpen,
    Layers3,
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
        title: 'My Services',
        href: '/dashboard#my-services',
        icon: Layers3,
    },
    {
        title: 'Service Marketplace',
        href: '/purchase',
        icon: ShoppingCart,
    },
    {
        title: 'License Center',
        href: '/sandbox-licenses',
        icon: KeyRound,
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
    const mainNavItems: NavItem[] = [
        ...baseNavItems,
        ...(operator?.enabled
            ? [
                  { title: 'Operator', href: '/operator', icon: Crown },
                  {
                      title: 'Product Manager',
                      href: '/operator#product-manager',
                      icon: PackageOpen,
                  },
                  {
                      title: 'Ops Command Center',
                      href: '/operator/ops',
                      icon: Activity,
                  },
              ]
            : []),
    ];

    return (
        <Sidebar collapsible="icon" variant="inset">
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
                <NavMain items={mainNavItems} />
            </SidebarContent>

            <SidebarFooter>
                <NavFooter items={footerNavItems} className="mt-auto" />
                <NavUser />
            </SidebarFooter>
        </Sidebar>
    );
}
