<?php

declare(strict_types=1);

namespace App\Services\Licensing\CodeBridge;

use App\Services\Licensing\Kslp\KslpSigner;
use DateTimeImmutable;
use DateTimeZone;
use DomainException;
use PDO;
use Throwable;

final class CodeBridgeRenewalService
{
    public function __construct(private PDO $db, private KslpSigner $signer) {}

    public function renew(string $credential, array $request, int $now): string
    {
        if (strlen($credential) < 32 || strlen($credential) > 4096 || ($request['product'] ?? null) !== 'KMJ_CODEBRIDGE' || ! is_int($request['sequence'] ?? null) || $request['sequence'] < -1 || count($request) !== 4) {
            throw new DomainException('CODEBRIDGE_ACCESS_DENIED');
        }
        foreach (['tenant', 'device'] as $key) {
            if (! is_string($request[$key] ?? null) || ! preg_match('/\A[A-Za-z0-9_-]{1,64}\z/D', $request[$key])) {
                throw new DomainException('CODEBRIDGE_ACCESS_DENIED');
            }
        }
        $driver = $this->db->getAttribute(PDO::ATTR_DRIVER_NAME);
        if (! in_array($driver, ['sqlite', 'mysql', 'pgsql'], true) || $this->db->inTransaction()) {
            throw new DomainException('CODEBRIDGE_STORAGE_UNAVAILABLE');
        }
        $lock = $driver === 'sqlite' ? '' : ' FOR UPDATE';
        $this->db->beginTransaction();
        try {
            $device = $this->one('SELECT * FROM codebridge_device_credentials WHERE token_hash = ?'.$lock, [hash('sha256', $credential)]);
            if (! $device || $device['revoked_at'] !== null || (int) $device['expires_at_epoch'] <= $now || $device['tenant_id'] !== $request['tenant'] || $device['device_id'] !== $request['device']) {
                throw new DomainException('CODEBRIDGE_ACCESS_DENIED');
            }
            $license = $this->one('SELECT * FROM kslp_licenses WHERE id = ?'.$lock, [$device['license_id']]);
            if (! $license || $license['product'] !== 'KMJ_CODEBRIDGE' || $license['customer_id'] !== $device['tenant_id'] || $license['status'] !== 'active' || $license['revoked_at'] !== null || self::timestamp($license['starts_at']) > $now || self::timestamp($license['expires_at']) <= $now) {
                throw new DomainException('CODEBRIDGE_ACCESS_DENIED');
            }
            $activation = $this->one('SELECT * FROM kslp_activations WHERE id = ? AND license_id = ?'.$lock, [$device['activation_id'], $license['id']]);
            if (! $activation || $activation['deactivated_at'] !== null || $activation['server_identity'] !== $device['server_identity']) {
                throw new DomainException('CODEBRIDGE_ACCESS_DENIED');
            }
            $policy = $this->one('SELECT features, limits FROM plans WHERE code = ? AND status = ?', ['codebridge.'.$license['plan'], 'active']);
            if (! $policy) {
                throw new DomainException('CODEBRIDGE_POLICY_UNAVAILABLE');
            }
            $featureMap = json_decode($policy['features'], true, 32, JSON_THROW_ON_ERROR);
            $limits = json_decode($policy['limits'], true, 32, JSON_THROW_ON_ERROR);
            if (! is_array($featureMap) || ! is_array($limits)) {
                throw new DomainException('CODEBRIDGE_POLICY_UNAVAILABLE');
            }
            $features = [];
            foreach ($featureMap as $feature => $enabled) {
                if (! in_array($feature, ['read', 'write', 'execute'], true) || ! is_bool($enabled)) {
                    throw new DomainException('CODEBRIDGE_POLICY_UNAVAILABLE');
                }
                if ($enabled) {
                    $features[] = $feature;
                }
            }
            $count = $this->one('SELECT COUNT(*) AS total FROM codebridge_device_credentials c JOIN kslp_activations a ON a.id = c.activation_id AND a.license_id = c.license_id WHERE c.license_id = ? AND c.revoked_at IS NULL AND c.expires_at_epoch > ? AND a.deactivated_at IS NULL', [$license['id'], $now]);
            if (! is_int($limits['devices'] ?? null) || (int) $count['total'] > $limits['devices']) {
                throw new DomainException('CODEBRIDGE_DEVICE_LIMIT');
            }
            $previous = (int) $device['lease_sequence'];
            if ($previous < 0 || $previous >= 9007199254740991 || $request['sequence'] > $previous) {
                throw new DomainException('CODEBRIDGE_SEQUENCE_CONFLICT');
            }
            $exp = min($now + 86400, self::timestamp($license['expires_at']), (int) $device['expires_at_epoch']);
            $grace = min($exp + 172800, $license['grace_until'] ? self::timestamp($license['grace_until']) : $exp, (int) $device['expires_at_epoch']);
            $jti = bin2hex(random_bytes(16));
            $claims = ['v' => 1, 'product' => 'KMJ_CODEBRIDGE', 'tenant' => $device['tenant_id'], 'device' => $device['device_id'], 'license_id' => $license['id'], 'activation_id' => $activation['id'], 'jti' => $jti, 'sequence' => $previous + 1, 'iat' => $now, 'nbf' => $now, 'exp' => $exp, 'grace_until' => max($exp, $grace), 'features' => $features, 'limits' => $limits];
            $token = (new CodeBridgeLeaseEncoder)->encode($claims, $this->signer, $now);
            $update = $this->db->prepare('UPDATE codebridge_device_credentials SET lease_sequence = ? WHERE id = ? AND lease_sequence = ?');
            $update->execute([$previous + 1, $device['id'], $previous]);
            if ($update->rowCount() !== 1) {
                throw new DomainException('CODEBRIDGE_SEQUENCE_CONFLICT');
            }
            $audit = $this->db->prepare('INSERT INTO kslp_license_events (license_id, actor_id, action, reason, correlation_id, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)');
            $audit->execute([$license['id'], 'codebridge-device:'.$device['device_id'], 'codebridge_lease_renewed', 'Authenticated device renewal', self::uuid(), json_encode(['activation_id' => $activation['id'], 'sequence' => $previous + 1, 'jti' => $jti], JSON_THROW_ON_ERROR), gmdate('Y-m-d H:i:s', $now)]);
            $this->db->commit();

            return $token;
        } catch (Throwable $error) {
            if ($this->db->inTransaction()) {
                $this->db->rollBack();
            }
            throw $error;
        }
    }

    private function one(string $sql, array $values): array|false
    {
        $statement = $this->db->prepare($sql);
        $statement->execute($values);

        return $statement->fetch(PDO::FETCH_ASSOC);
    }

    private static function timestamp(string $value): int
    {
        return (new DateTimeImmutable($value, new DateTimeZone('UTC')))->getTimestamp();
    }

    private static function uuid(): string
    {
        $hex = bin2hex(random_bytes(16));

        return substr($hex, 0, 8).'-'.substr($hex, 8, 4).'-4'.substr($hex, 13, 3).'-a'.substr($hex, 17, 3).'-'.substr($hex, 20, 12);
    }
}
