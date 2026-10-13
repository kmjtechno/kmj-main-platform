<?php

declare(strict_types=1);

namespace App\Services\Operator;

/**
 * Single source of truth for the Super Admin modules.
 *
 * Navigation and any future module hub read this list, so adding a module is one
 * entry here plus its route. Visibility is NOT decided here: callers must already
 * be behind PlatformOwnerAccess (verified email + passkey + owner flag).
 *
 * @phpstan-type Module array{id: string, group: string, title: string, description: string, href: string, icon: string}
 */
final class OperatorModules
{
    /**
     * @return list<Module>
     */
    public static function all(): array
    {
        return [
            [
                'id' => 'operator-overview',
                'group' => 'Overview',
                'title' => 'Super Admin',
                'description' => 'Platform owner overview and orders.',
                'href' => '/operator',
                'icon' => 'Crown',
            ],
            [
                'id' => 'directory',
                'group' => 'Customers',
                'title' => 'Customers & Organizations',
                'description' => 'Directory of customers, organizations and entitlements.',
                'href' => '/operator/directory',
                'icon' => 'Users',
            ],
            [
                'id' => 'products',
                'group' => 'Products',
                'title' => 'Product Manager',
                'description' => 'Catalog, availability and licensing flags per product.',
                'href' => '/operator#product-manager',
                'icon' => 'PackageOpen',
            ],
            [
                'id' => 'licensing',
                'group' => 'Licensing',
                'title' => 'Licensing Governance',
                'description' => 'KSLP issuers, licenses and revocation.',
                'href' => '/operator/kslp',
                'icon' => 'KeyRound',
            ],
            [
                'id' => 'payments',
                'group' => 'Commerce',
                'title' => 'Gateway Settings',
                'description' => 'Payment gateway readiness and credential status.',
                'href' => '/operator/payments',
                'icon' => 'CreditCard',
            ],
            [
                'id' => 'ops',
                'group' => 'Operations',
                'title' => 'Ops Command Center',
                'description' => 'Delivery, queues and operational readiness.',
                'href' => '/operator/ops',
                'icon' => 'Activity',
            ],
        ];
    }

    /**
     * @return array<string, list<Module>>
     */
    public static function grouped(): array
    {
        $groups = [];
        foreach (self::all() as $module) {
            $groups[$module['group']][] = $module;
        }

        return $groups;
    }
}
