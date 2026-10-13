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
    Users,
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

type OperatorModule = {
    id: string;
    title: string;
    href: string;
    icon: string;
};

const operatorIcons: Record<string, NavItem['icon']> = {
    Activity,
    CreditCard,
    Crown,
    KeyRound,
    PackageOpen,
    Users,
};

export function AppSidebar() {
    const operator = usePage().props.operator as
        | { enabled?: boolean; modules?: OperatorModule[] }
        | undefined;
    const operatorItems: NavItem[] = operator?.enabled
        ? (operator.modules ?? []).map((module) => ({
              title: module.title,
              href: module.href,
              icon: operatorIcons[module.icon] ?? Crown,
          }))
        : [];
    const mainNavItems: NavItem[] = [...baseNavItems, ...operatorItems];

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
