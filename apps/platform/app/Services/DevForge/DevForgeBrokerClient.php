<?php

namespace App\Services\DevForge;

use RuntimeException;

final class DevForgeBrokerClient
{
    private const SOCKET = '/run/kmj-devforge/control.sock';

    /**
     * All host operations are performed by a separately provisioned,
     * root-owned, allowlisted broker over a local Unix domain socket.
     * PHP never gets a Docker socket, shell, sudo, SSH, or host path parameter.
     *
     * @return array<string, mixed>
     */
    public function status(): array
    {
        try {
            return $this->send('status');
        } catch (RuntimeException) {
            return [
                'broker_ready' => false,
                'state' => 'not_provisioned',
                'healthy' => false,
                'busy' => false,
                'last_action' => null,
                'last_error' => null,
                'access' => 'loopback_only',
            ];
        }
    }

    /**
     * @return array<string, mixed>
     */
    public function action(string $action): array
    {
        if (! in_array($action, ['install', 'start', 'stop', 'restart'], true)) {
            throw new RuntimeException('Unsupported DevForge action.');
        }

        return $this->send($action);
    }

    /**
     * @return array<string, mixed>
     */
    private function send(string $action): array
    {
        $errorNo = 0;
        $errorMessage = '';
        $stream = @stream_socket_client(
            'unix://'.self::SOCKET,
            $errorNo,
            $errorMessage,
            2,
            STREAM_CLIENT_CONNECT,
        );
        if ($stream === false) {
            throw new RuntimeException('DevForge host broker is not provisioned or unavailable.');
        }

        try {
            stream_set_timeout($stream, 3);
            $request = json_encode(['action' => $action], JSON_THROW_ON_ERROR);
            if (@fwrite($stream, $request."\n") !== strlen($request) + 1) {
                throw new RuntimeException('DevForge host broker request failed.');
            }

            $line = fgets($stream, 2049);
            if ($line === false || strlen($line) > 2048 || ! str_ends_with($line, "\n")) {
                throw new RuntimeException('DevForge host broker response unavailable.');
            }

            $response = json_decode($line, true, 16, JSON_THROW_ON_ERROR);
            if (! is_array($response) || ! isset($response['ok']) || ! is_bool($response['ok'])) {
                throw new RuntimeException('DevForge host broker response invalid.');
            }

            if (! $response['ok']) {
                $reason = (string) ($response['error'] ?? 'ACTION_REJECTED');
                throw new RuntimeException('DevForge action blocked: '.substr($reason, 0, 80));
            }

            return $response;
        } catch (\JsonException $exception) {
            throw new RuntimeException('DevForge host broker protocol invalid.', 0, $exception);
        } finally {
            fclose($stream);
        }
    }
}
