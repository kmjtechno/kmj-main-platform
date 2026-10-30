import { Link, usePage } from '@inertiajs/react';
import {
    Activity,
    Boxes,
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

export function AppSidebar() {
    const operator = usePage().props.operator as
        | { enabled?: boolean }
        | undefined;
    const ownerBusiness: NavItem[] = operator?.enabled
        ? [
              { title: 'Command Center', href: '/operator', icon: Crown },
              {
                  title: 'Products',
                  href: '/operator/products',
                  icon: PackageOpen,
              },
              {
                  title: 'Customers & Organizations',
                  href: '/operator/directory',
                  icon: Users,
              },
          ]
        : [];
    const ownerCommerce: NavItem[] = operator?.enabled
        ? [
              {
                  title: 'Orders & Fulfillment',
                  href: '/operator#commercial-orders',
                  icon: ShoppingCart,
              },
              {
                  title: 'Payments',
                  href: '/operator/payments',
                  icon: CreditCard,
              },
              {
                  title: 'KMJ Licensing Hub · Owner',
                  href: '/operator/kslp',
                  icon: KeyRound,
              },
          ]
        : [];
    const ownerSystems: NavItem[] = operator?.enabled
        ? [
              {
                  title: 'Operations & Audit',
                  href: '/operator/ops',
                  icon: Activity,
              },
              {
                  title: 'CodeBridge Controls',
                  href: '/operator/codebridge/owner-plan',
                  icon: Boxes,
              },
          ]
        : [];

    return (
        <Sidebar
            collapsible="icon"
            variant="inset"
            className="kmj-premium-sidebar"
        >
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
                {operator?.enabled && (
                    <>
                        <NavMain
                            items={ownerBusiness}
                            label="Business · Owner"
                        />
                        <NavMain
                            items={ownerCommerce}
                            label="Commerce & Access"
                        />
                        <NavMain items={ownerSystems} label="Systems & Trust" />
                    </>
                )}
            </SidebarContent>

            <SidebarFooter>
                <NavFooter items={footerNavItems} className="mt-auto" />
                <NavUser />
            </SidebarFooter>
        </Sidebar>
    );
}
