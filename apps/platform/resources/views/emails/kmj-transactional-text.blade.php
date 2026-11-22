{{ $heading }}

{{ $greeting }}

{{ $intro }}

@foreach ($details as $detail)
{{ $detail['label'] }}: {{ $detail['value'] }}
@endforeach

@if ($actionUrl !== null && $actionText !== null)
{{ $actionText }}:
{!! $actionUrl !!}
@endif

@if ($notice !== null)
{{ $notice }}
@endif

Need help? Contact info@kmjtechno.com.
Never share your passwords, one-time codes or private recovery links.

KMJ TECHNO — INNOVATE | BUILD | SCALE
https://kmjtechno.com
info@kmjtechno.com

This is a transactional service notification, not a marketing message.
