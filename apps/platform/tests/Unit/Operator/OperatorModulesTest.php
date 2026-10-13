<?php

declare(strict_types=1);

namespace Tests\Unit\Operator;

use App\Services\Operator\OperatorModules;
use PHPUnit\Framework\TestCase;

final class OperatorModulesTest extends TestCase
{
    public function test_modules_have_the_required_shape_and_unique_ids(): void
    {
        $modules = OperatorModules::all();

        $this->assertNotEmpty($modules);
        $this->assertCount(count($modules), array_unique(array_column($modules, 'id')));

        foreach ($modules as $module) {
            $this->assertSame(['id', 'group', 'title', 'description', 'href', 'icon'], array_keys($module));
            $this->assertMatchesRegularExpression('#^/operator(/[a-z-]+|\#[a-z-]+)?$#', $module['href']);
            $this->assertNotSame('', $module['title']);
        }
    }

    public function test_grouping_preserves_module_order_and_membership(): void
    {
        $flattened = array_merge(...array_values(OperatorModules::grouped()));

        $this->assertCount(count(OperatorModules::all()), $flattened);
        $this->assertSame('Overview', array_key_first(OperatorModules::grouped()));
    }
}
