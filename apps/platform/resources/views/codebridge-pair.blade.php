<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Approve KMJ CodeBridge device</title>
    <style>
        body { margin: 0; font-family: system-ui, sans-serif; background:#090909; color:#f5f5f5; }
        main { max-width:720px; margin:7vh auto; padding:32px; background:#151515; border:1px solid #333; border-radius:16px; }
        h1 { margin-top:0; } .muted { color:#aaa; } .card { background:#0f0f0f; padding:18px; border-radius:10px; margin:18px 0; }
        label { display:block; margin:12px 0 6px; } select, input { width:100%; box-sizing:border-box; padding:10px; background:#090909; color:#fff; border:1px solid #444; border-radius:8px; }
        button { margin-top:18px; background:#ed010b; color:#fff; border:0; padding:12px 18px; border-radius:8px; font-weight:700; cursor:pointer; }
        .ok { padding:12px; background:#12351a; border-radius:8px; } .err { padding:12px; background:#431515; border-radius:8px; }
    </style>
</head>
<body>
<main>
    <h1>Connect KMJ CodeBridge</h1>
    <p class="muted">Approve only a VPS/device you recognize. The installer never needs your KMJ password.</p>

    @if (session('status'))
        <div class="ok">{{ session('status') }}</div>
    @endif

    @if ($errors->any())
        <div class="err">{{ $errors->first() }}</div>
    @endif

    @if (!$pairing)
        <form method="GET" action="{{ route('codebridge.pair') }}">
            <label for="code">Pairing code</label>
            <input id="code" name="code" value="{{ $code }}" placeholder="ABCD-EFGH" autocomplete="off" required>
            <button type="submit">Check device</button>
        </form>
    @else
        <div class="card">
            <strong>{{ $pairing['device_name'] }}</strong>
            <p>Device ID: {{ $pairing['device_id'] }}</p>
            <p>Platform: {{ $pairing['platform'] }} / {{ $pairing['arch'] }}</p>
            <p>Project: {{ $pairing['project_name'] }} ({{ $pairing['project_id'] }})</p>
            <p>Permissions: {{ implode(', ', $pairing['permissions']) }}</p>
            <p>Expires: {{ $pairing['expires_at'] }}</p>
        </div>

        @if (count($pairing['organizations']) === 0)
            <div class="err">No eligible KMJ CodeBridge license is available for an organization you manage.</div>
        @else
            <form method="POST" action="{{ route('codebridge.pair.approve') }}">
                @csrf
                <input type="hidden" name="code" value="{{ $pairing['code'] }}">
                <label for="tenant_id">KMJ organization</label>
                <select id="tenant_id" name="tenant_id" required>
                    @foreach ($pairing['organizations'] as $organization)
                        <option value="{{ $organization['id'] }}">{{ $organization['name'] }}</option>
                    @endforeach
                </select>
                <button type="submit">Approve CodeBridge device</button>
            </form>
        @endif
    @endif
</main>
</body>
</html>
