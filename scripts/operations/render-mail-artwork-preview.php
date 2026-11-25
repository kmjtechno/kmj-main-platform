<?php

declare(strict_types=1);

// CI-only fixed synthetic fixture. No mail sending, user data or production database.
if (getenv('GITHUB_ACTIONS') !== 'true' || getenv('APP_ENV') !== 'testing' || getenv('MAIL_MAILER') !== 'array' || getenv('DB_CONNECTION') !== 'sqlite') {
    throw new RuntimeException('CI_TEST_ONLY');
}
$platform = dirname(__DIR__, 2).'/apps/platform';
require $platform.'/vendor/autoload.php';
$app = require $platform.'/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
$dir = $platform.'/visual-results/mail-artwork';
if (! is_dir($dir) && ! mkdir($dir, 0755, true)) {
    throw new RuntimeException('PREVIEW_DIRECTORY_FAILED');
}
foreach (App\Services\Mail\EnterpriseMailTheme::catalog() as $id => $palette) {
    if (App\Services\Mail\EnterpriseMailTheme::artworkBase($palette) === null) {
        throw new RuntimeException('ARTWORK_MISSING '.$id);
    }
    $html = view('emails.kmj-native-outgoing', [
        'heading' => 'Project status update',
        'body' => "Hello,\n\nYour project update is ready. This is a synthetic no-send preview of official KMJ correspondence.",
        'senderAddress' => 'info@kmjtechno.com',
        'previewTheme' => $palette,
    ])->render();
    if (file_put_contents($dir.'/'.$id.'.html', $html) === false) {
        throw new RuntimeException('PREVIEW_WRITE_FAILED');
    }
}
echo "BLADE_MAIL_PREVIEWS=6 SMTP_SEND=NONE\n";
