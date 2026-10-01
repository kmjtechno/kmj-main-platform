<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Connect KMJ CodeBridge</title>
    <style>
        body { font-family: system-ui, sans-serif; background: #0a0a0a; color: #f5f5f5; margin: 0; }
        main { max-width: 680px; margin: 8vh auto; padding: 32px; background: #151515; border: 1px solid #333; border-radius: 16px; }
        h1 { margin-top: 0; } li { margin: 12px 0; line-height: 1.45; }
        .account { color: #bbb; } button { background: #ed010b; color: white; border: 0; border-radius: 8px; padding: 12px 18px; font-weight: 700; cursor: pointer; }
    </style>
</head>
<body>
<main>
    <h1>Connect KMJ CodeBridge</h1>
    <p class="account">Signed in as {{ $user->email }}</p>
    <p>Approve access for the CodeBridge MCP connection. Server-side authorization still limits every request to your configured tenant, devices, projects, and permissions.</p>
    <ul>
        @foreach ($scopes as $scope => $description)
            <li><strong>{{ $scope }}</strong><br>{{ $description }}</li>
        @endforeach
    </ul>
    <form method="POST" action="{{ route('codebridge.oauth.approve', ['uid' => $uid]) }}">
        @csrf
        <button type="submit">Approve CodeBridge connection</button>
    </form>
</main>
</body>
</html>
