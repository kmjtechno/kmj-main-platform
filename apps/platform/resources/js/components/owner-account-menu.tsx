import { Link, router } from '@inertiajs/react';
import { LogOut, Settings, ShieldCheck } from 'lucide-react';
import {
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import type { User } from '@/types';

/** The locked owner shell must not depend on a generated Wayfinder route bundle. */
export default function OwnerAccountMenu({ user }: { user: User }) {
    return (
        <>
            <DropdownMenuLabel className="px-3 py-2">
                <strong className="block truncate text-sm">{user.name}</strong>
                <span className="text-muted-foreground block truncate text-xs">
                    {user.email}
                </span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
                <Link
                    href="/settings/profile"
                    className="flex cursor-pointer items-center gap-2"
                >
                    <Settings className="size-4" aria-hidden="true" />
                    My profile
                </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
                <Link
                    href="/settings/security"
                    className="flex cursor-pointer items-center gap-2"
                >
                    <ShieldCheck className="size-4" aria-hidden="true" />
                    Security settings
                </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
                <button
                    type="button"
                    onClick={() => {
                        router.flushAll();
                        router.post('/logout');
                    }}
                    data-test="logout-button"
                    className="flex w-full cursor-pointer items-center gap-2 text-left"
                >
                    <LogOut className="size-4" aria-hidden="true" />
                    Log out
                </button>
            </DropdownMenuItem>
        </>
    );
}
