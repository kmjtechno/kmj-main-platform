@if ($artwork !== null)
<tr><td bgcolor="{{ $theme['footer'] }}" style="padding:0;background:{{ $theme['footer'] }};border-top:3px solid {{ $theme['accent'] }};">
<img src="{{ $artwork }}/footer.jpg" width="100%" alt="KMJ TECHNO — Enterprise Software &amp; Solutions" style="display:block;width:100%;height:auto;border:0;color:#ffffff;">
</td></tr>
<tr><td class="kmj-pad kmj-gutter" bgcolor="{{ $theme['footer'] }}" style="padding:14px 26px 20px;background:{{ $theme['footer'] }};color:#ffffff;">
<p style="margin:0 0 9px;font-size:13px;line-height:20px;"><a href="https://kmjtechno.com" style="color:#ffffff;text-decoration:underline;">www.kmjtechno.com</a> &nbsp; | &nbsp; <a href="mailto:info@kmjtechno.com" style="color:#ffffff;text-decoration:underline;">info@kmjtechno.com</a></p>
<p style="margin:0;border-top:1px solid #64748b;padding-top:10px;font-size:12px;line-height:19px;color:#e5edf8;">{{ $footerNotice }}</p>
</td></tr>
@else
<tr><td class="kmj-pad kmj-gutter" bgcolor="{{ $theme['footer'] }}" style="padding:26px 36px;background:{{ $theme['footer'] }};color:#ffffff;border-top:4px solid {{ $theme['accent'] }};">
<p style="margin:0 0 8px;color:#ffffff;font-size:19px;line-height:26px;font-weight:bold;"><span style="color:#ff3853;">KMJ</span> TECHNO</p>
<p style="margin:0 0 15px;color:#e5edf8;font-size:13px;line-height:20px;">Enterprise Software &amp; Solutions</p>
<p style="margin:0 0 6px;font-size:13px;line-height:22px;"><a href="https://kmjtechno.com" style="color:#ffffff;text-decoration:underline;">www.kmjtechno.com</a> &nbsp; | &nbsp; <a href="mailto:info@kmjtechno.com" style="color:#ffffff;text-decoration:underline;">info@kmjtechno.com</a></p>
<p style="margin:0 0 16px;color:#e5edf8;font-size:12px;line-height:20px;">India | Global Delivery</p>
<p style="margin:0;border-top:1px solid #64748b;padding-top:13px;font-size:12px;line-height:19px;color:#e5edf8;">{{ $footerNotice }}</p>
</td></tr>
@endif
