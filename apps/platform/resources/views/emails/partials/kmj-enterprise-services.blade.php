<tr><td class="kmj-pad" bgcolor="{{ $theme['tint'] }}" style="padding:18px 26px;background:{{ $theme['tint'] }};border-top:1px solid #dce3ed;">
<p style="margin:0 0 12px;color:{{ $theme['accent'] }};font-size:11px;line-height:18px;font-weight:bold;letter-spacing:1px;">KMJ TECHNO SOLUTIONS</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%;border-collapse:collapse;table-layout:fixed;">
<tr>
@foreach (['Enterprise Software', 'Projection & Calibration', 'Remote Access'] as $service)
<td valign="top" width="33%" style="padding:5px 6px;text-align:center;font-size:12px;line-height:18px;color:#17263b;"><strong style="color:{{ $theme['accent'] }};">&#9670;</strong><br>{{ $service }}</td>
@endforeach
</tr><tr>
@foreach (['CloudOS & Infrastructure', 'AI & Automation', 'Licensing'] as $service)
<td valign="top" width="33%" style="padding:5px 6px;text-align:center;font-size:12px;line-height:18px;color:#17263b;"><strong style="color:{{ $theme['accent'] }};">&#9670;</strong><br>{{ $service }}</td>
@endforeach
</tr>
</table>
</td></tr>
