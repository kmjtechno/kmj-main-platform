<tr><td class="kmj-pad" bgcolor="{{ $theme['tint'] }}" style="padding:18px 12px;background:{{ $theme['tint'] }};border-top:1px solid #dce3ed;">
<p style="margin:0 0 12px;color:{{ $theme['accent'] }};font-size:11px;line-height:18px;font-weight:bold;letter-spacing:1px;">KMJ TECHNO SOLUTIONS</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%;border-collapse:collapse;table-layout:fixed;">
<tr class="kmj-services-row">
@foreach (['enterprise' => 'Enterprise Software', 'projection' => 'Projection & Calibration', 'remote' => 'Remote Access', 'cloud' => 'CloudOS & Infrastructure', 'ai' => 'AI & Automation'] as $icon => $service)
<td class="kmj-service-cell" valign="top" width="20%" style="padding:6px 3px;border-right:1px solid #dce3ed;text-align:center;font-size:12px;line-height:17px;font-weight:bold;color:#17263b;overflow-wrap:normal;">
@if ($artwork !== null)
<img src="{{ $artwork }}/{{ $icon }}.png" width="36" alt="" style="display:block;width:36px;height:auto;margin:0 auto 7px;border:0;">
@endif
{{ $service }}
</td>
@endforeach
</tr>
</table>
</td></tr>
