<?php

declare(strict_types=1);

namespace App\Services\Mail;

use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

final class EnterpriseMailTheme
{
    public const DEFAULT = 'signature-red';

    /** @return array<string, array{label:string,header:string,footer:string,accent:string,ink:string,tint:string,layout:string}> */
    public static function catalog(): array
    {
        return [
            'signature-red' => ['label' => 'Signature Red (default)', 'header' => '#0b1425', 'footer' => '#101b30', 'accent' => '#c71935', 'ink' => '#ffffff', 'tint' => '#fff2f4', 'layout' => 'signature'],
            'blue-wave' => ['label' => 'Sapphire Wave', 'header' => '#071b44', 'footer' => '#082756', 'accent' => '#1555cf', 'ink' => '#ffffff', 'tint' => '#edf5ff', 'layout' => 'wave'],
            'white-geometric' => ['label' => 'Executive White', 'header' => '#f4f7fb', 'footer' => '#102743', 'accent' => '#165bd7', 'ink' => '#111c30', 'tint' => '#f0f5fc', 'layout' => 'geometric'],
            'blue-letterhead' => ['label' => 'Corporate Letterhead', 'header' => '#ffffff', 'footer' => '#082c60', 'accent' => '#154db8', 'ink' => '#111c30', 'tint' => '#eff5ff', 'layout' => 'letterhead'],
            'blue-signature' => ['label' => 'Global Signature', 'header' => '#061933', 'footer' => '#081d3b', 'accent' => '#126bc5', 'ink' => '#ffffff', 'tint' => '#eaf4ff', 'layout' => 'global'],
            'executive-gold' => ['label' => 'Executive Gold', 'header' => '#101b2a', 'footer' => '#152234', 'accent' => '#94600d', 'ink' => '#ffffff', 'tint' => '#fbf5e8', 'layout' => 'gold'],
        ];
    }

    /**
     * Fixed first-party static artwork; never use request data as a path.
     *
     * @param array<string, string> $theme
     */
    public static function artworkBase(array $theme): ?string
    {
        $id = match ($theme['layout'] ?? null) {
            'signature' => 'signature-red',
            'wave' => 'blue-wave',
            'geometric' => 'white-geometric',
            'letterhead' => 'blue-letterhead',
            'global' => 'blue-signature',
            'gold' => 'executive-gold',
            default => null,
        };

        if ($id === null) {
            return null;
        }

        foreach (['header.jpg', 'footer.jpg', 'enterprise.png', 'projection.png', 'remote.png', 'cloud.png', 'ai.png'] as $file) {
            if (! is_file(public_path('assets/brand/mail/'.$id.'/'.$file))) {
                return null;
            }
        }

        return 'https://kmjtechno.com/assets/brand/mail/'.$id;
    }

    public static function installed(): bool
    {
        return Schema::hasColumn('kmj_native_smtp_settings', 'enterprise_theme');
    }

    public static function selected(): string
    {
        $id = self::installed()
            ? DB::table('kmj_native_smtp_settings')->where('id', 1)->value('enterprise_theme')
            : null;

        return is_string($id) && isset(self::catalog()[$id]) ? $id : self::DEFAULT;
    }

    /** @return array{label:string,header:string,footer:string,accent:string,ink:string,tint:string,layout:string} */
    public static function palette(?string $id = null): array
    {
        return self::catalog()[$id ?? self::selected()] ?? self::catalog()[self::DEFAULT];
    }
}
