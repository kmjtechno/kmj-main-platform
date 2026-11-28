<?php
/**
 * Candidate-only FPM auto_prepend_file guard. Install outside the document
 * root, root-owned, immutable to stage workers; configure ONLY the exact
 * candidate FastCGI location after independent review. Never load globally.
 * A request is rejected before Laravel bootstrap if storage is unavailable.
 */
declare(strict_types=1);

const KMJ_A892_APP = '/home/kmjstage/releases/a892b0d5d851129a9d8ed00c1af1390da6ee584f/apps/platform';
const KMJ_A892_SOURCE = '/home/kmjstage/shared/storage-app-b2e69decab3a';
const KMJ_A892_ARTWORK = '/home/kmjstage/shared/product-artwork';

function kmj_a892_mount_record_valid(string $mountinfo, string $target): bool
{
    // Exact fixed paths have no mountinfo escaping. Reject ambiguous stacked
    // mounts, absent mountpoints, malformed records and unsafe mount flags.
    $matches = 0;
    foreach (explode("\n", $mountinfo) as $line) {
        $fields = explode(' ', $line);
        if (count($fields) < 7 || $fields[4] !== $target) {
            continue;
        }
        $matches++;
        if ($matches !== 1 || !in_array('-', $fields, true)) {
            return false;
        }
        $flags = explode(',', $fields[5]);
        foreach (['rw', 'nosuid', 'nodev', 'noexec'] as $required) {
            if (!in_array($required, $flags, true)) {
                return false;
            }
        }
    }
    return $matches === 1;
}

function kmj_a892_storage_ready(): bool
{
    $target = KMJ_A892_APP . '/storage/app';
    $source = KMJ_A892_SOURCE;
    clearstatcache(true);
    if (is_link($target) || is_link($source) ||
        realpath($target) !== $target || realpath($source) !== $source ||
        !is_dir($target) || !is_dir($source) ||
        !is_readable($target) || !is_writable($target)) {
        return false;
    }
    $a = @stat($target);
    $b = @stat($source);
    if (!is_array($a) || !is_array($b) ||
        $a['dev'] !== $b['dev'] || $a['ino'] !== $b['ino']) {
        return false;
    }
    $artwork = $target . '/private/product-artwork';
    if (!is_link($artwork) || realpath($artwork) !== KMJ_A892_ARTWORK) {
        return false;
    }
    $info = @file_get_contents('/proc/self/mountinfo', false, null, 0, 4194305);
    return is_string($info) && strlen($info) <= 4194304 &&
        kmj_a892_mount_record_valid($info, $target);
}

// CLI imports are diagnostic-only; HTTP execution must be exact candidate FPM.
if (PHP_SAPI !== 'cli') {
    if (PHP_SAPI !== 'fpm-fcgi' ||
        ($_SERVER['SCRIPT_FILENAME'] ?? '') !== KMJ_A892_APP . '/public/index.php' ||
        !kmj_a892_storage_ready()) {
        http_response_code(503);
        header('Cache-Control: no-store');
        header('Content-Type: text/plain; charset=utf-8');
        echo "Staging temporarily unavailable.\n";
        exit;
    }
}
