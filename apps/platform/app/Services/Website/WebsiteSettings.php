<?php

namespace App\Services\Website;

use App\Models\OperatorActionAudit;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Throwable;

/**
 * Owner-editable public website settings. Every read falls back to the shipped
 * defaults, so public pages work before the migration and with an empty table.
 */
final class WebsiteSettings
{
    public const SECTIONS = ['trust', 'products', 'capabilities', 'ecosystem', 'industries', 'roadmap'];

    public const HEADINGS = ['products', 'capabilities', 'ecosystem', 'industries', 'roadmap'];

    /** @var array<string, array<string, mixed>>|null */
    private ?array $stored = null;

    /** False until the migration has run. */
    public function available(): bool
    {
        return Schema::hasTable('website_settings');
    }

    /** @return array<string, mixed> */
    public static function defaults(): array
    {
        return [
            'features' => [
                'smooth_scrolling' => true,
                'scroll_animations' => true,
                'scroll_to_top' => true,
                'kristi' => true,
                'language_button' => false,
            ],
            'sections' => array_fill_keys(self::SECTIONS, true),
            'headings' => [
                'products' => ['title' => 'Our Flagship Products', 'subtitle' => 'Powerful solutions for immersive experiences, intelligent operations and real-world impact.'],
                'capabilities' => ['title' => 'What We Build', 'subtitle' => 'From idea to global deployment — we build any kind of software, system or immersive experience.'],
                'ecosystem' => ['title' => 'A Complete and Connected Ecosystem', 'subtitle' => 'Our products work together to create a unified platform for creation, control, deployment and growth.'],
                'industries' => ['title' => 'Industries We Serve', 'subtitle' => 'Real solutions for real-world challenges.'],
                'roadmap' => ['title' => 'Our Roadmap', 'subtitle' => 'Building a future-ready ecosystem.'],
            ],
            'roadmap' => [
                ['title' => 'Now', 'summary' => 'Available Products', 'text' => 'Review platform and product availability.'],
                ['title' => 'Next', 'summary' => 'Enhanced Features', 'text' => 'Advanced capabilities and new integrations.'],
                ['title' => 'In Development', 'summary' => 'New Products', 'text' => 'Ongoing development and testing.'],
                ['title' => 'Future', 'summary' => 'Ecosystem Expansion', 'text' => 'More industries, more tools and global reach.'],
            ],
            // Placeholder profiles. The page stays hidden until the owner publishes it.
            'team' => [
                'published' => false,
                'intro' => 'The people building KMJ TECHNO.',
                'members' => array_map(static fn (int $number): array => [
                    'name' => 'Member name '.$number,
                    'role' => 'Role / designation',
                    'bio' => 'Sample profile. Replace this text from the admin panel.',
                    'photo' => null,
                    'linkedin' => null,
                    'visible' => true,
                ], [1, 2, 3, 4]),
            ],
        ];
    }

    /** @return array<string, mixed> */
    public function all(): array
    {
        $defaults = self::defaults();
        $stored = $this->stored();

        return [
            'features' => array_replace($defaults['features'], array_intersect_key($stored['features'] ?? [], $defaults['features'])),
            'sections' => array_replace($defaults['sections'], array_intersect_key($stored['sections'] ?? [], $defaults['sections'])),
            'headings' => array_replace($defaults['headings'], array_intersect_key($stored['headings'] ?? [], $defaults['headings'])),
            'roadmap' => count($stored['roadmap'] ?? []) === 4 ? array_values($stored['roadmap']) : $defaults['roadmap'],
            'team' => array_replace($defaults['team'], $stored['team'] ?? []),
        ];
    }

    /** Settings every public page may read. Team profiles are not included. */
    public function shared(): array
    {
        $all = $this->all();

        return [
            'features' => $all['features'],
            'sections' => $all['sections'],
            'headings' => $all['headings'],
            'roadmap' => $all['roadmap'],
            'team_published' => (bool) $all['team']['published'],
        ];
    }

    /** True when a visible profile on the published team page uses this photo. */
    public function isPublicPhoto(string $path): bool
    {
        $team = $this->all()['team'];

        return (bool) $team['published'] && collect($team['members'])
            ->contains(fn (array $member): bool => ($member['visible'] ?? false) && ($member['photo'] ?? null) === $path);
    }

    /** @param array<string, mixed> $values */
    public function save(array $values, int $userId): void
    {
        DB::transaction(function () use ($values, $userId): void {
            foreach ($values as $key => $value) {
                DB::table('website_settings')->updateOrInsert(
                    ['key' => $key],
                    ['value' => json_encode($value, JSON_THROW_ON_ERROR), 'updated_by' => $userId, 'updated_at' => now(), 'created_at' => now()],
                );
            }

            OperatorActionAudit::query()->create([
                'actor_user_id' => $userId,
                'action' => 'website.settings.updated',
                'outcome' => 'success',
                'metadata' => ['keys' => array_keys($values)],
            ]);
        });

        $this->stored = null;
    }

    /** @return array<string, array<string, mixed>> */
    private function stored(): array
    {
        if ($this->stored !== null) {
            return $this->stored;
        }

        try {
            if (! $this->available()) {
                return $this->stored = [];
            }

            $rows = DB::table('website_settings')->pluck('value', 'key');
        } catch (Throwable $error) {
            // A settings problem must never take the public website down.
            report($error);

            return $this->stored = [];
        }

        return $this->stored = $rows
            ->map(fn (mixed $value): mixed => json_decode((string) $value, true))
            ->filter(fn (mixed $value): bool => is_array($value))
            ->all();
    }
}
