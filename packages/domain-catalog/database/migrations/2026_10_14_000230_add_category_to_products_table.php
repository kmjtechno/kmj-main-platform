<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('products', function (Blueprint $table): void {
            $table->string('category', 32)->default('other')->index();
        });

        // Explicit, known KMJ catalog families; never infer ownership,
        // purchase access or licensing from a visual category.
        $categories = [
            'cloud' => ['kmj-cloudos', 'kmj-cloud-nexus'],
            'cinema' => [
                'kmj-cinema-platform', 'kmj-360-dome', 'kmj-cinema-player',
                'kmj-immersive-cinema-suite', 'kmj-5d-cinema', 'kmj-7d-cinema',
                'kmj-9d-cinema', 'kmj-12d-cinema', 'kmj-14d-cinema',
                'kmj-16d-cinema', 'kmj-5dx-cinema',
            ],
            'industrial' => ['kmj-calibration-pro'],
            'developer' => [
                'kmj-codebridge', 'kmj-forge', 'kmj-agent', 'kmj-ai-gateway',
                'kmj-automate', 'kmj-desktop-commander',
            ],
            'business' => [
                'kmj-omnidesk', 'kmj-connect', 'kmj-licensing-hub',
                'kmj-creative-studio', 'kmj-ai-support',
            ],
        ];

        foreach ($categories as $category => $slugs) {
            DB::table('products')
                ->whereIn('slug', $slugs)
                ->where('category', 'other')
                ->update(['category' => $category]);
        }
    }

    public function down(): void
    {
        // SQLite does not permit dropping a column while an index still
        // references it. Reverse the indexed add in dependency order.
        Schema::table('products', function (Blueprint $table): void {
            $table->dropIndex('products_category_index');
        });
        Schema::table('products', function (Blueprint $table): void {
            $table->dropColumn('category');
        });
    }
};
