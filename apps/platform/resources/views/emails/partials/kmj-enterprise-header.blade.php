@if ($artwork !== null)
<tr><td bgcolor="{{ $theme['header'] }}" style="padding:0;background:{{ $theme['header'] }};color:{{ $theme['ink'] }};border-top:3px solid {{ $theme['accent'] }};">
<a href="https://kmjtechno.com" style="display:block;color:{{ $theme['ink'] }};text-decoration:none;"><img src="{{ $artwork }}/header.jpg" width="100%" alt="KMJ TECHNO — INNOVATE | BUILD | SCALE" style="display:block;width:100%;height:auto;border:0;color:{{ $theme['ink'] }};font-size:18px;line-height:24px;"></a>
</td></tr>
@else
<tr><td height="5" bgcolor="{{ $theme['accent'] }}" style="height:5px;font-size:0;line-height:5px;background:{{ $theme['accent'] }};">&nbsp;</td></tr>
<tr><td class="kmj-pad kmj-gutter" bgcolor="{{ $theme['header'] }}" style="padding:26px 36px 22px;background:{{ $theme['header'] }};color:{{ $theme['ink'] }};border-left:{{ $theme['layout'] === 'letterhead' ? '12px solid '.$theme['accent'] : '0' }};">
@if ($theme['layout'] === 'geometric')
<p style="margin:0 0 16px;color:{{ $theme['accent'] }};font-size:11px;font-weight:bold;letter-spacing:1px;">KMJTECHNO.COM &nbsp; / &nbsp; INDIA · GLOBAL DELIVERY</p>
@endif
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="width:100%;border-collapse:collapse;">
<tr><td align="{{ $theme['layout'] === 'letterhead' ? 'center' : 'left' }}">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;">
<tr><td width="70" valign="middle"><a href="https://kmjtechno.com"><img class="kmj-brand-mark" src="https://kmjtechno.com/assets/brand/kmj-sender-avatar.png" width="64" height="64" alt="KMJ TECHNO" style="display:block;width:64px;height:64px;border:0;"></a></td>
<td valign="middle" style="padding-left:12px;">
<a href="https://kmjtechno.com" style="text-decoration:none;color:{{ $theme['ink'] }};">
<span class="kmj-brand-name" style="font-size:26px;line-height:31px;font-weight:bold;color:{{ $theme['ink'] }};"><span style="color:#e52240;">KMJ</span> TECHNO</span>
</a>
<p class="kmj-tagline" style="margin:4px 0 0;font-size:15px;line-height:21px;font-weight:700;letter-spacing:.4px;color:{{ $theme['ink'] }};">INNOVATE | BUILD | SCALE</p>
</td></tr></table>
</td></tr>
<tr><td style="padding-top:18px;font-size:13px;line-height:21px;color:{{ $theme['ink'] }};text-align:{{ $theme['layout'] === 'letterhead' ? 'center' : 'left' }};">Enterprise Software &nbsp;·&nbsp; Projection &amp; Calibration &nbsp;·&nbsp; Remote Access &nbsp;·&nbsp; Cloud &amp; AI</td></tr>
</table>
</td></tr>
<tr><td bgcolor="{{ $theme['header'] }}" style="background:{{ $theme['header'] }};">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr><td height="5" width="{{ $theme['layout'] === 'wave' ? '68%' : '35%' }}" bgcolor="{{ $theme['accent'] }}" style="font-size:0;line-height:5px;">&nbsp;</td><td bgcolor="{{ $theme['footer'] }}" style="font-size:0;line-height:5px;">&nbsp;</td></tr></table>
</td></tr>
@endif
