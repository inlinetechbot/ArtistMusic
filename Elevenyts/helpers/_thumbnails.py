# ==========================================================
# Copyright (c) 2026 ArtistBots
# All Rights Reserved.
#
# Project      : ArtistBots API Telegram Music Bot
# Powered By   : Artist
# Type         : API Based Telegram Music Bot
#
# Bot          : @ArtistApibot
# Channel      : https://t.me/artistbots
# GitHub       : https://github.com/elevenyts
#
# Unauthorized copying, modification, or redistribution
# of this source code without permission is prohibited.
# ==========================================================

import os
import re
import asyncio
import aiohttp
import base64

from PIL import (
    Image,
    ImageDraw,
    ImageEnhance,
    ImageFilter,
    ImageFont,
    ImageOps
)

from Elevenyts import config
from Elevenyts.helpers import Track

# ─────────────────────────────
# PALETTE
# ─────────────────────────────

PURPLE      = (124,  58, 237)
PURPLE_MID  = (139,  92, 246)
PURPLE_SOFT = (167, 139, 250)
PURPLE_GLOW = ( 80,  30, 200)
WHITE       = (255, 255, 255)

SIZE = (1280, 720)
FONT_BASE = "Elevenyts/helpers/"

_f = "QXJ0aXN0Ym90cw=="

def _decode_f():
    decoded = base64.b64decode(_f).decode("utf-8")
    return f"✦ {decoded} ✦"


# ─────────────────────────────
# GRADIENTS
# ─────────────────────────────

def _h_grad(size, c1, c2):
    w, h = size
    img  = Image.new("RGBA", size)
    d    = ImageDraw.Draw(img)
    for x in range(w):
        t = x / w
        r = int(c1[0]+(c2[0]-c1[0])*t)
        g = int(c1[1]+(c2[1]-c1[1])*t)
        b = int(c1[2]+(c2[2]-c1[2])*t)
        d.line((x,0,x,h), fill=(r,g,b,255))
    return img

def _v_grad(size, c1, c2):
    w, h = size
    img  = Image.new("RGBA", size)
    d    = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        r = int(c1[0]+(c2[0]-c1[0])*t)
        g = int(c1[1]+(c2[1]-c1[1])*t)
        b = int(c1[2]+(c2[2]-c1[2])*t)
        d.line((0,y,w,y), fill=(r,g,b,255))
    return img


# ─────────────────────────────
# BACKGROUND — song image light blur
# ─────────────────────────────

def _build_background(song_img):
    bg = ImageOps.fit(song_img.convert("RGB"), SIZE, method=Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(6))
    bg = ImageEnhance.Brightness(bg).enhance(0.52)
    bg = bg.convert("RGBA")
    return bg


# ─────────────────────────────
# GLASS CARD — blurred song inside
# ─────────────────────────────

def _glass_card(base, song_img, x, y, w, h, radius=40):
    blurred = ImageOps.fit(song_img.convert("RGB"), SIZE, method=Image.LANCZOS)
    blurred = blurred.filter(ImageFilter.GaussianBlur(38))
    blurred = ImageEnhance.Brightness(blurred).enhance(0.38)
    blurred = ImageEnhance.Color(blurred).enhance(1.5)
    blurred = blurred.convert("RGBA")

    card_crop = blurred.crop((x, y, x+w, y+h))

    tint = Image.new("RGBA", (w,h), (5, 2, 16, 155))
    card_crop.paste(tint, (0,0), tint)

    mask = Image.new("L", (w,h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0,0,w-1,h-1), radius=radius, fill=255)
    card_crop.putalpha(mask)
    base.paste(card_crop, (x,y), card_crop)

    # Outer border
    bdr = Image.new("RGBA", (w,h), (0,0,0,0))
    ImageDraw.Draw(bdr).rounded_rectangle((0,0,w-1,h-1), radius=radius,
                                           outline=(255,255,255,35), width=1)
    base.paste(bdr, (x,y), bdr)

    # Top specular streak
    sw   = int(w * 0.45)
    spec = Image.new("RGBA", (sw, 2), (0,0,0,0))
    half = sw // 2
    for sx in range(sw):
        t = sx/half if sx < half else 1-(sx-half)/max(half,1)
        ImageDraw.Draw(spec).line((sx,0,sx,2), fill=(255,255,255,int(115*t)))
    base.paste(spec, (x+(w-sw)//2, y+1), spec)


# ─────────────────────────────
# ALBUM ART
# ─────────────────────────────

def _paste_album_art(base, raw, ax, ay, sz=430, radius=34):
    halo = Image.new("RGBA", SIZE, (0,0,0,0))
    for i in range(55):
        a = int(58*(1-i/55))
        ImageDraw.Draw(halo).rounded_rectangle(
            (ax-i, ay-i, ax+sz+i, ay+sz+i),
            radius=radius+i, fill=(*PURPLE_GLOW, a))
    halo = halo.filter(ImageFilter.GaussianBlur(22))
    base.paste(halo, (0,0), halo)

    art  = ImageOps.fit(raw, (sz,sz), method=Image.LANCZOS)
    mask = Image.new("L", (sz,sz), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0,0,sz-1,sz-1), radius=radius, fill=255)
    art.putalpha(mask)
    base.paste(art, (ax,ay), art)

    bdr = Image.new("RGBA", (sz,sz), (0,0,0,0))
    ImageDraw.Draw(bdr).rounded_rectangle((0,0,sz-1,sz-1), radius=radius,
                                           outline=(255,255,255,45), width=2)
    base.paste(bdr, (ax,ay), bdr)


# ─────────────────────────────
# PILL & GRADIENT TEXT
# ─────────────────────────────

def _pill(base, x, y, w, h, fill, outline=None, radius=None):
    radius = radius or h//2
    layer  = Image.new("RGBA", (w,h), (0,0,0,0))
    d      = ImageDraw.Draw(layer)
    d.rounded_rectangle((0,0,w-1,h-1), radius=radius,
                         fill=fill, outline=outline,
                         width=1 if outline else 0)
    base.paste(layer, (x,y), layer)

def _gradient_text(base, draw, xy, text, font, c1=WHITE, c2=PURPLE_SOFT):
    tw   = int(draw.textlength(text, font=font))
    th   = font.size + 14
    grad = _h_grad((tw+10, th), c1, c2)
    alpha = Image.new("RGBA", (tw+10,th), (0,0,0,0))
    ImageDraw.Draw(alpha).text((0,0), text, font=font, fill=(255,255,255,255))
    grad.putalpha(alpha.getchannel("A"))
    base.paste(grad, xy, grad)


# ─────────────────────────────
# FROSTED BUTTON
# ─────────────────────────────

def _frosted_btn(base, x, y, sz, is_play=False):
    flat = base.convert("RGB").convert("RGBA")
    crop = flat.crop((x,y,x+sz,y+sz))
    crop = crop.filter(ImageFilter.GaussianBlur(10))

    if is_play:
        fill = _v_grad((sz,sz), (*PURPLE,235), (*PURPLE_MID,255))
        crop.paste(fill, (0,0), fill)
    else:
        tint = Image.new("RGBA", (sz,sz), (255,255,255,18))
        crop.paste(tint, (0,0), tint)

    mask = Image.new("L", (sz,sz), 0)
    ImageDraw.Draw(mask).ellipse((0,0,sz-1,sz-1), fill=255)
    crop.putalpha(mask)
    base.paste(crop, (x,y), crop)

    bdr = Image.new("RGBA", (sz,sz), (0,0,0,0))
    ImageDraw.Draw(bdr).ellipse((0,0,sz-1,sz-1),
                                 outline=(255,255,255,38), width=1)
    base.paste(bdr, (x,y), bdr)

    shim = Image.new("RGBA", (sz,sz), (0,0,0,0))
    for i in range(8):
        a = int(80*(1-i/8))
        ImageDraw.Draw(shim).arc(
            (i+3,i+3,sz-3-i,sz//2),
            start=215, end=325,
            fill=(255,255,255,a), width=1)
    base.paste(shim, (x,y), shim)


# ─────────────────────────────
# PLAYER ICONS
# ─────────────────────────────

def _draw_triangle(layer, cx, cy, size, direction="right", color=(255,255,255,230)):
    d = ImageDraw.Draw(layer)
    w = int(size*0.85)
    if direction == "right":
        pts = [(cx-w//2+2,cy-size//2),(cx-w//2+2,cy+size//2),(cx+w//2,cy)]
    else:
        pts = [(cx+w//2-2,cy-size//2),(cx+w//2-2,cy+size//2),(cx-w//2,cy)]
    d.polygon(pts, fill=color)

def _draw_double_triangle(layer, cx, cy, size, direction="right", color=(255,255,255,215)):
    gap = int(size*0.28)
    if direction == "right":
        _draw_triangle(layer, cx-gap, cy, size, "right", color)
        _draw_triangle(layer, cx+gap, cy, size, "right", color)
    else:
        _draw_triangle(layer, cx+gap, cy, size, "left", color)
        _draw_triangle(layer, cx-gap, cy, size, "left", color)

def _draw_shuffle_icon(layer, cx, cy, size, color=(255,255,255,130)):
    d  = ImageDraw.Draw(layer)
    s  = size//2
    lw = max(2, size//8)
    d.line([(cx-s,cy-s//2),(cx+s,cy+s//2)], fill=color, width=lw)
    d.line([(cx-s,cy+s//2),(cx+s,cy-s//2)], fill=color, width=lw)

def _draw_repeat_icon(layer, cx, cy, size, color=(255,255,255,130)):
    d  = ImageDraw.Draw(layer)
    r  = size//2
    lw = max(2, size//8)
    d.arc([cx-r,cy-r,cx+r,cy+r], start=40, end=320, fill=color, width=lw)
    d.polygon([(cx+r-2,cy-3),(cx+r+5,cy),(cx+r-2,cy+3)], fill=color)

def _draw_volume_icon(layer, cx, cy, size, color=(255,255,255,130)):
    d = ImageDraw.Draw(layer)
    s = size//2
    pts = [(cx-s,cy-s//3),(cx-s//3,cy-s//3),(cx,cy-s),
           (cx,cy+s),(cx-s//3,cy+s//3),(cx-s,cy+s//3)]
    d.polygon(pts, fill=color)
    lw = max(1, size//10)
    d.arc([cx-2,cy-s//2,cx+s//2,cy+s//2], start=300, end=60, fill=color, width=lw)
    d.arc([cx,cy-s+2,cx+s,cy+s-2], start=300, end=60, fill=color, width=lw)


# ─────────────────────────────
# PLAYER
# ─────────────────────────────

def _draw_player(base, x, y):
    BTN    = 56
    PLAY   = 78
    FG     = (255,255,255,210)
    FG_DIM = (255,255,255,125)
    ICON   = 15
    cx     = x - 30

    def _icon(sz): return Image.new("RGBA",(sz,sz),(0,0,0,0))

    _frosted_btn(base, cx, y, BTN)
    sh = _icon(BTN)
    _draw_shuffle_icon(sh, BTN//2, BTN//2, ICON+2, FG_DIM)
    base.paste(sh, (cx,y), sh)
    cx += BTN+14

    _frosted_btn(base, cx, y, BTN)
    pv = _icon(BTN)
    _draw_double_triangle(pv, BTN//2, BTN//2, ICON, "left", FG)
    base.paste(pv, (cx,y), pv)
    cx += BTN+16

    px, py = cx, y-11
    for rad, alp in [(85,14),(60,26),(40,42)]:
        g = Image.new("RGBA", SIZE, (0,0,0,0))
        ImageDraw.Draw(g).ellipse(
            (px-rad+PLAY//2, py-rad+PLAY//2,
             px+rad+PLAY//2, py+rad+PLAY//2),
            fill=(*PURPLE_GLOW, alp))
        g = g.filter(ImageFilter.GaussianBlur(24))
        base.paste(g, (0,0), g)
    _frosted_btn(base, px, py, PLAY, is_play=True)
    pl = _icon(PLAY)
    _draw_triangle(pl, PLAY//2+6, PLAY//2, 30, "right", WHITE)
    base.paste(pl, (px,py), pl)
    cx += PLAY+18

    _frosted_btn(base, cx, y, BTN)
    nx = _icon(BTN)
    _draw_double_triangle(nx, BTN//2, BTN//2, ICON, "right", FG)
    base.paste(nx, (cx,y), nx)
    cx += BTN+14

    _frosted_btn(base, cx, y, BTN)
    rp = _icon(BTN)
    _draw_repeat_icon(rp, BTN//2, BTN//2, ICON+2, FG_DIM)
    base.paste(rp, (cx,y), rp)
    cx += BTN+20

    vi = _icon(30)
    _draw_volume_icon(vi, 14, 15, 13, FG_DIM)
    base.paste(vi, (cx,y+14), vi)
    cx += 44

    sw = 148
    trk = Image.new("RGBA",(sw,6),(0,0,0,0))
    ImageDraw.Draw(trk).rounded_rectangle((0,0,sw-1,5), radius=3, fill=(255,255,255,22))
    base.paste(trk, (cx,y+26), trk)
    fw    = 90
    sfill = _h_grad((fw,6), PURPLE, PURPLE_SOFT)
    sm    = Image.new("L",(fw,6),0)
    ImageDraw.Draw(sm).rounded_rectangle((0,0,fw-1,5), radius=3, fill=255)
    sfill.putalpha(sm)
    base.paste(sfill, (cx,y+26), sfill)
    knob = Image.new("RGBA",(12,12),(0,0,0,0))
    ImageDraw.Draw(knob).ellipse((0,0,11,11), fill=(*PURPLE_SOFT,255))
    ImageDraw.Draw(knob).ellipse((3,3,8,8),   fill=(255,255,255,210))
    base.paste(knob, (cx+fw-6,y+23), knob)


# ─────────────────────────────
# PROGRESS BAR
# ─────────────────────────────

def _draw_progress(base, draw, x, y, width, cur, end, font):
    draw.text((x,y-26), cur, font=font, fill=(255,255,255,135))
    rw = int(draw.textlength(end, font=font))
    draw.text((x+width-rw,y-26), end, font=font, fill=(255,255,255,135))

    trk = Image.new("RGBA",(width,5),(0,0,0,0))
    ImageDraw.Draw(trk).rounded_rectangle((0,0,width-1,4), radius=3, fill=(255,255,255,20))
    base.paste(trk, (x,y), trk)

    fw    = int(width*0.18)
    pfill = _h_grad((fw,5), PURPLE, PURPLE_SOFT)
    pm    = Image.new("L",(fw,5),0)
    ImageDraw.Draw(pm).rounded_rectangle((0,0,fw-1,4), radius=3, fill=255)
    pfill.putalpha(pm)
    base.paste(pfill, (x,y), pfill)

    knob = Image.new("RGBA",(14,14),(0,0,0,0))
    ImageDraw.Draw(knob).ellipse((0,0,13,13), fill=(*PURPLE_SOFT,255))
    ImageDraw.Draw(knob).ellipse((4,4,9,9),   fill=(255,255,255,210))
    base.paste(knob, (x+fw-7,y-4), knob)


# ─────────────────────────────
# MAIN CLASS
# ─────────────────────────────

def trim_to_width(text: str, font, max_w: int) -> str:
    ellipsis = "…"
    if font.getlength(text) <= max_w:
        return text
    for i in range(len(text) - 1, 0, -1):
        if font.getlength(text[:i] + ellipsis) <= max_w:
            return text[:i] + ellipsis
    return ellipsis


class Thumbnail:

    def __init__(self):
        try:
            self.f_title  = ImageFont.truetype(FONT_BASE+"Raleway-Bold.ttf", 44)
            self.f_artist = ImageFont.truetype(FONT_BASE+"Raleway-Bold.ttf", 24)
            self.f_badge  = ImageFont.truetype(FONT_BASE+"Inter-Light.ttf",  18)
            self.f_brand  = ImageFont.truetype(FONT_BASE+"Raleway-Bold.ttf", 32)
            self.f_power  = ImageFont.truetype(FONT_BASE+"Inter-Light.ttf",  17)
            self.f_sig    = ImageFont.truetype(FONT_BASE+"Raleway-Bold.ttf", 22)
        except OSError:
            self.f_title  = ImageFont.load_default()
            self.f_artist = ImageFont.load_default()
            self.f_badge  = ImageFont.load_default()
            self.f_brand  = ImageFont.load_default()
            self.f_power  = ImageFont.load_default()
            self.f_sig    = ImageFont.load_default()

    async def save_thumb(self, output_path: str, url: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                with open(output_path, "wb") as f:
                    f.write(await resp.read())
        return output_path

    async def generate(self, song: Track, size=(1280, 720)) -> str:
        try:
            temp   = f"cache/temp_{song.id}.jpg"
            output = f"cache/{song.id}_ultra.png"

            if os.path.exists(output):
                return output

            await self.save_thumb(temp, song.thumbnail)

            return await asyncio.get_event_loop().run_in_executor(
                None,
                self._generate_sync,
                temp,
                output,
                song,
                size
            )

        except Exception:
            return config.DEFAULT_THUMB

    def _generate_sync(self, temp, output, song, size=(1280, 720)) -> str:
        try:
            W, H = SIZE
            raw  = Image.open(temp).convert("RGBA")

            # Sharp+lightblur background
            base = _build_background(raw)
            draw = ImageDraw.Draw(base)

            # ── GLASS CARD ───────────────────────────────
            CX, CY, CW, CH = 36, 82, 1208, 488
            _glass_card(base, raw, CX, CY, CW, CH, radius=42)

            # ── ALBUM ART ────────────────────────────────
            _paste_album_art(base, raw, ax=62, ay=104, sz=436, radius=34)

            tx = 532

            # ── SIGNATURE TOP LEFT ───────────────────────
            draw.text((48, 24), _decode_f(), font=self.f_sig,
                      fill=(255,255,255,180))

            # ── NOW PLAYING BADGE ────────────────────────
            badge = "▶  NOW PLAYING"
            bw = int(draw.textlength(badge, font=self.f_badge))+44
            _pill(base, tx, 126, bw, 36,
                  (*PURPLE,65), (*PURPLE_SOFT,80), 18)
            draw.text((tx+22,135), badge, font=self.f_badge,
                      fill=(*PURPLE_SOFT,255))

            # ── TITLE ────────────────────────────────────
            clean_title = re.sub(r"\W+", " ", song.title).title()
            title = trim_to_width(clean_title, self.f_title, 640)
            _gradient_text(base, draw, (tx,190), title,
                           self.f_title, WHITE, PURPLE_SOFT)

            # ── ARTIST ───────────────────────────────────
            draw.text((tx,264), song.channel_name[:40],
                      font=self.f_artist, fill=(200,190,255,190))

            # ── DIVIDER ──────────────────────────────────
            div = Image.new("RGBA",(640,1),(0,0,0,0))
            ImageDraw.Draw(div).line((0,0,639,0), fill=(255,255,255,18), width=1)
            base.paste(div, (tx,310), div)

            # ── CHIPS ────────────────────────────────────
            chip_y = 322
            is_live = getattr(song, "is_live", False)
            chips  = [
                (f"👁  {song.view_count or 'Unknown'}",  (*PURPLE,55),  (*PURPLE_SOFT,75)),
                ("✦ HD Audio" if not is_live else "🔴 LIVE", (255,255,255,14),(255,255,255,30)),
                (f"⏱  {song.duration}",                  (255,255,255,14),(255,255,255,30)),
            ]
            ccx = tx
            for label, fc, oc in chips:
                cw = int(draw.textlength(label, font=self.f_badge))+38
                _pill(base, ccx, chip_y, cw, 38, fc, oc, 19)
                draw.text((ccx+19,chip_y+9), label, font=self.f_badge,
                          fill=(255,255,255,185))
                ccx += cw+12

            # ── PLAYER ───────────────────────────────────
            _draw_player(base, tx+38, 396)

            # ── PROGRESS ─────────────────────────────────
            end_text = "LIVE" if is_live else song.duration
            _draw_progress(base, draw, tx, 502, 718,
                           "0:01", end_text, self.f_badge)

            # ── BRAND ────────────────────────────────────
            sep = Image.new("RGBA",(W,1),(0,0,0,0))
            ImageDraw.Draw(sep).line((80,0,W-80,0), fill=(255,255,255,15), width=1)
            base.paste(sep, (0,H-102), sep)

            wm1 = "OpusMusic"
            wm2 = "Powered by Alfabots"
            w1  = int(draw.textlength(wm1, font=self.f_brand))
            w2  = int(draw.textlength(wm2, font=self.f_power))
            _gradient_text(base, draw, ((W-w1)//2, H-90), wm1,
                           self.f_brand, WHITE, PURPLE_SOFT)
            draw.text(((W-w2)//2, H-52), wm2,
                      font=self.f_power, fill=(255,255,255,110))

            base.save(output)
            try:    os.remove(temp)
            except: pass
            return output

        except Exception:
            return config.DEFAULT_THUMB
