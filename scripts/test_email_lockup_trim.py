#!/usr/bin/env python3
"""The email lockup trim must stay a pure, lossless crop of the canonical lockup.

No resampling, recolouring or redesign: every pixel of the trimmed email asset must
equal the canonical pixel at the fixed crop offset, so the approved logo is unchanged
and only its empty margin is removed (the tagline then renders larger at the same width).
"""
from pathlib import Path
import struct
import unittest
import zlib

BRAND = Path(__file__).resolve().parents[1] / "apps/platform/public/assets/brand"
CANON = BRAND / "kmj-email-lockup-dark.png"
TRIM = BRAND / "kmj-email-lockup-dark-trim.png"
VIEWS = Path(__file__).resolve().parents[1] / "apps/platform/resources/views/emails"
OFFSET = (15, 70)
SIZE = (1057, 265)
BYTES_PER_PIXEL = {6: 4, 2: 3}


def decode(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, idat, ihdr = 8, b"", None
    while pos < len(data):
        n, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if kind == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat += body
    width, height, depth, ctype, _c, _f, interlace = ihdr
    assert depth == 8 and ctype in BYTES_PER_PIXEL and interlace == 0, ihdr
    bpp = BYTES_PER_PIXEL[ctype]
    raw, stride = zlib.decompress(idat), width * bpp
    rows, prev = [], bytearray(stride)
    for y in range(height):
        base = y * (stride + 1)
        ft, line = raw[base], bytearray(raw[base + 1:base + 1 + stride])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if ft == 1:
                line[i] = (line[i] + a) & 255
            elif ft == 2:
                line[i] = (line[i] + b) & 255
            elif ft == 3:
                line[i] = (line[i] + ((a + b) >> 1)) & 255
            elif ft == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 255
            else:
                assert ft == 0, ft
        rows.append(bytes(line))
        prev = line
    return width, height, bpp, rows


class EmailLockupTrimTest(unittest.TestCase):
    def test_trim_is_pixel_identical_crop_of_canonical(self):
        cw, ch, cbpp, crows = decode(CANON)
        tw, th, tbpp, trows = decode(TRIM)
        self.assertEqual((tw, th), SIZE)
        self.assertEqual(cbpp, tbpp)
        x0, y0 = OFFSET
        for y in range(th):
            self.assertEqual(
                trows[y],
                crows[y0 + y][x0 * cbpp:(x0 + tw) * cbpp],
                f"row {y} differs from the canonical lockup",
            )

    def test_all_email_templates_use_reference_readable_html_wordmark(self):
        for name in ("kmj-transactional", "kmj-auth-transactional", "kmj-native-outgoing"):
            html = (VIEWS / f"{name}.blade.php").read_text(encoding="utf-8")
            self.assertIn("/assets/brand/kmj-sender-avatar.png", html, name)
            self.assertIn('class="kmj-tagline"', html, name)
            self.assertIn('font-size:15px;line-height:21px;font-weight:700', html, name)
            self.assertNotIn("kmj-email-lockup-dark-trim.png", html, name)
            self.assertIn('width="64" height="64" alt="KMJ TECHNO"', html, name)


if __name__ == "__main__":
    unittest.main()
