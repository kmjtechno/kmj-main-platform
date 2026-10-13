<?php

declare(strict_types=1);

namespace App\Services\AiProviders;

use Closure;
use InvalidArgumentException;

/**
 * SSRF guard for provider endpoints: HTTPS on 443 only, no credentials in the URL,
 * a hostname (never an IP literal) on the approved list, and every DNS answer public.
 * The first validated address is returned so the caller can pin the connection to it.
 */
final class EndpointGuard
{
    /** @param Closure(string): list<string>|null $resolver */
    public function __construct(private readonly ?Closure $resolver = null) {}

    /**
     * @param  list<string>  $approvedHosts
     * @return array{host: string, ip: string, base: string}
     */
    public function validate(string $url, array $approvedHosts): array
    {
        $parts = parse_url($url);
        if (! is_array($parts) || ($parts['scheme'] ?? '') !== 'https') {
            throw new InvalidArgumentException('endpoint_scheme');
        }
        if (isset($parts['user']) || isset($parts['pass'])) {
            throw new InvalidArgumentException('endpoint_userinfo');
        }
        if (isset($parts['port']) && (int) $parts['port'] !== 443) {
            throw new InvalidArgumentException('endpoint_port');
        }
        if (isset($parts['query']) || isset($parts['fragment'])) {
            throw new InvalidArgumentException('endpoint_path');
        }
        $host = strtolower((string) ($parts['host'] ?? ''));
        if ($host === '' || filter_var($host, FILTER_VALIDATE_IP) !== false || str_starts_with($host, '[')
            || preg_match('/\A(?=.{1,253}\z)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\z/', $host) !== 1) {
            throw new InvalidArgumentException('endpoint_host');
        }
        $path = (string) ($parts['path'] ?? '');
        if (preg_match('#\A(/[A-Za-z0-9._~-]+)*/?\z#', $path) !== 1 || str_contains($path, '..')) {
            throw new InvalidArgumentException('endpoint_path');
        }
        if (! in_array($host, array_map('strtolower', $approvedHosts), true)) {
            throw new InvalidArgumentException('endpoint_not_approved');
        }

        $addresses = ($this->resolver ?? self::systemResolver(...))($host);
        if ($addresses === []) {
            throw new InvalidArgumentException('endpoint_dns');
        }
        foreach ($addresses as $address) {
            if (! self::isPublic($address)) {
                throw new InvalidArgumentException('endpoint_private');
            }
        }

        return ['host' => $host, 'ip' => $addresses[0], 'base' => 'https://'.$host.rtrim($path, '/')];
    }

    public static function isPublic(string $address): bool
    {
        $packed = @inet_pton($address);
        if ($packed === false) {
            return false;
        }
        if (strlen($packed) === 16 && str_starts_with($packed, str_repeat("\0", 10)."\xff\xff")) {
            $address = (string) inet_ntop(substr($packed, 12));
        }
        if (filter_var($address, FILTER_VALIDATE_IP, FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE) === false) {
            return false;
        }
        if (filter_var($address, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4) !== false) {
            $long = ip2long($address);
            // 100.64.0.0/10 (carrier-grade NAT) is not covered by the PHP flags.
            if ($long !== false && ($long & 0xFFC00000) === 0x64400000) {
                return false;
            }
        }

        return true;
    }

    /** @return list<string> */
    private static function systemResolver(string $host): array
    {
        $records = @dns_get_record($host, DNS_A | DNS_AAAA);
        $addresses = [];
        foreach (is_array($records) ? $records : [] as $record) {
            $ip = $record['ip'] ?? $record['ipv6'] ?? null;
            if (is_string($ip)) {
                $addresses[] = $ip;
            }
        }

        return array_values(array_unique($addresses));
    }
}
