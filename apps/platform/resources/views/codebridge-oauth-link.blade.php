<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Connect KMJ CodeBridge</title>
    <style>
        body { font-family: system-ui, sans-serif; background: #0a0a0a; color: #f5f5f5; margin: 0; }
        main { max-width: 760px; margin: 6vh auto; padding: 32px; background: #151515; border: 1px solid #333; border-radius: 16px; }
        h1, h2 { margin-top: 0; } li { margin: 12px 0; line-height: 1.45; }
        .account, .muted { color: #bbb; }
        .service, .registration { background: #0e0e0e; border: 1px solid #2f2f2f; border-radius: 12px; padding: 18px; margin: 18px 0; }
        .eyebrow { color: #ff2933; font-size: 12px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
        .status { display: inline-flex; border: 1px solid #3d3d3d; border-radius: 999px; padding: 5px 9px; font-size: 11px; margin-top: 8px; }
        button { background: #ed010b; color: white; border: 0; border-radius: 8px; padding: 12px 18px; font-weight: 700; cursor: pointer; }
    </style>
</head>
<body>
<main>
    <div class="eyebrow">KMJ TECHNO service authorization</div>
    <h1>Connect KMJ CodeBridge</h1>
    <p class="account">Signed in as {{ $user->email }}</p>

    <section class="service">
        <h2>{{ $service['name'] ?? 'KMJ CodeBridge' }}</h2>
        <p>{{ $service['summary'] ?? 'Secure AI coding bridge for authorized projects, devices, Git and quality-gate workflows.' }}</p>
        @if (!empty($service['lifecycle_label']))
            <span class="status">{{ $service['lifecycle_label'] }}</span>
        @endif
    </section>

    @if (count($registrations) > 0)
        <h2>Your CodeBridge access</h2>
        @foreach ($registrations as $registration)
            <section class="registration">
                <strong>{{ $registration['organization']['name'] }}</strong>
                @foreach ($registration['entitlements'] as $entitlement)
                    <p class="muted">
                        {{ $entitlement['product_name'] }} · {{ $entitlement['capability'] }} · {{ $entitlement['status'] }}
                    </p>
                @endforeach
            </section>
        @endforeach
    @else
        <section class="registration">
            <strong>KMJ CodeBridge service</strong>
            <p class="muted">
                This sign-in request is specifically for KMJ CodeBridge. No unrelated KMJ product is being authorized by this screen.
            </p>
        </section>
    @endif

    <p>Approve access for this CodeBridge MCP connection. Server-side authorization still limits every request to the account, devices, projects, and permissions granted to CodeBridge.</p>

    <ul>
        @foreach ($scopes as $scope => $description)
            <li><strong>{{ $scope }}</strong><br>{{ $description }}</li>
        @endforeach
    </ul>

    <form method="POST" action="{{ route('codebridge.oauth.continue.approve', ['uid' => $uid]) }}">
        @csrf
        <button type="submit">Approve KMJ CodeBridge</button>
    </form>
</main>
</body>
</html>
