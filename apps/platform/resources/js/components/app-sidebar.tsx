[Reading 73 lines from start (total: 73 lines, 0 remaining)]

import { Link, usePage } from '@inertiajs/react';
import { Activity, Crown, LayoutGrid, ShieldCheck } from 'lucide-react';
import AppLogo from '@/components/app-logo';
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

const customerNavItems: NavItem[] = [
    {
        title: 'My Services',
        href: dashboard(),
        icon: LayoutGrid,
    },
    {
        title: 'Security',
        href: securitySettings(),
        icon: ShieldCheck,
    },
];

export function AppSidebar() {
    const operator = usePage().props.operator as
        | { enabled?: boolean }
        | undefined;
    const mainNavItems: NavItem[] = [
        ...customerNavItems,
        ...(operator?.enabled
            ? [
                  { title: 'Operator', href: '/operator', icon: Crown },
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
                <NavUser />
            </SidebarFooter>
        </Sidebar>
    );
}

[executed on device: kmjtechnonetgmailcom (cbe1c3e2-c299-4851-9d11-9fafa86b4357)]