"""Almacenamiento: shows free space on both microSD cards (Anbernic stock OS, APPS section).

Draws straight to the framebuffer like the stock Clock app (Pillow + /dev/fb0) and reads
buttons from /dev/input/event1. A = what uses space in Roms, B / MENU = exit.
Run with --png <file> to render the main screen to an image instead (for testing over SSH).
"""
import mmap
import os
import shutil
import struct
import subprocess
import sys
from fcntl import ioctl

from PIL import Image, ImageDraw, ImageFont

W, H = 720, 480
FONT = "/usr/share/fonts/TTF/DejaVuSansMono.ttf"
FB_CFG = "/mnt/mod/ctrl/configs/fb.cfg"

BG = (18, 18, 24)
FG = (235, 235, 235)
DIM = (150, 150, 160)
ACCENT = (40, 110, 220)
BAR_BG = (55, 55, 65)
OK = (60, 170, 90)
WARN = (220, 160, 40)
FULL = (210, 60, 60)

# (title, subtitle, mount point)
VOLUMES = [
    ("SD 2 - Juegos", "/mnt/sdcard", "/mnt/sdcard"),
    ("SD 1 - Sistema", "Linux (/)", "/"),
    ("SD 1 - Apps", "/mnt/vendor", "/mnt/vendor"),
    ("SD 1 - Datos", "/mnt/data", "/mnt/data"),
    ("SD 1 - Visible", "/mnt/mmc", "/mnt/mmc"),
]

KEY_A, KEY_B, KEY_MENU = 304, 305, 312


def font(size):
    return ImageFont.truetype(FONT, size)


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit in ("GB", "TB") else f"{n:.0f} {unit}"
        n /= 1024


def bar_color(frac):
    return OK if frac < 0.75 else WARN if frac < 0.9 else FULL


def header(d, title):
    d.rectangle((0, 0, W, 52), fill=ACCENT)
    d.text((20, 26), title, font=font(26), fill=FG, anchor="lm")


def footer(d, text):
    d.text((20, H - 22), text, font=font(17), fill=DIM, anchor="lm")


def draw_main():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    header(d, "Almacenamiento")
    y = 66
    for title, sub, path in VOLUMES:
        try:
            u = shutil.disk_usage(path)
        except OSError:
            continue
        frac = u.used / u.total if u.total else 0
        d.text((20, y), title, font=font(21), fill=FG)
        d.text((260, y + 3), sub, font=font(16), fill=DIM)
        d.text((W - 20, y), f"{human(u.free)} libres", font=font(21), fill=FG, anchor="ra")
        y += 31
        d.rounded_rectangle((20, y, W - 20, y + 14), 6, fill=BAR_BG)
        d.rounded_rectangle((20, y, 20 + max(12, int((W - 40) * frac)), y + 14), 6, fill=bar_color(frac))
        y += 18
        d.text((20, y), f"Usado {human(u.used)} de {human(u.total)} ({frac * 100:.0f}%)", font=font(15), fill=DIM)
        y += 23
    footer(d, "A: ¿Qué ocupa espacio en Roms?     B / MENU: Salir")
    return img


def draw_message(text):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    header(d, "Almacenamiento")
    d.text((W // 2, H // 2), text, font=font(24), fill=FG, anchor="mm")
    return img


def roms_usage(root="/mnt/sdcard/Roms"):
    out = subprocess.run(["du", "-sk", "--", *[os.path.join(root, e) for e in os.listdir(root)]],
                         capture_output=True, text=True).stdout
    rows = []
    for line in out.splitlines():
        kb, path = line.split("\t", 1)
        if os.path.isdir(path):
            rows.append((int(kb) * 1024, os.path.basename(path)))
    return sorted(rows, reverse=True)


def draw_roms(rows, page, per_page=14):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    pages = max(1, (len(rows) + per_page - 1) // per_page)
    header(d, f"Roms en SD 2 ({page + 1}/{pages})")
    top = rows[0][0] if rows else 1
    y = 64
    for size, name in rows[page * per_page:(page + 1) * per_page]:
        d.text((20, y), name[:22], font=font(18), fill=FG)
        d.rounded_rectangle((300, y + 4, 300 + max(4, int(290 * size / top)), y + 18), 4, fill=ACCENT)
        d.text((W - 20, y), human(size), font=font(18), fill=FG, anchor="ra")
        y += 27
    footer(d, "◀ ▶: página     B: Volver     MENU: Salir")
    return img, pages


class Screen:
    def __init__(self):
        self.fb = os.open("/dev/fb0", os.O_RDWR)
        if os.path.exists(FB_CFG):  # same screen setup the stock apps use
            with open(FB_CFG, "rb") as f:
                ioctl(self.fb, 0x4601, bytearray(f.read()))
        ioctl(self.fb, 0x4611, 0)
        # The framebuffer is double-buffered (720x960) and the frontend may leave either page
        # on screen (pan 0,0 or 0,480), so draw every frame into all pages.
        try:
            with open("/sys/class/graphics/fb0/virtual_size") as f:
                self.pages = max(1, int(f.read().split(",")[1]) // H)
        except (OSError, ValueError, IndexError):
            self.pages = 1
        self.mm = mmap.mmap(self.fb, W * H * 4 * self.pages)

    def show(self, img):
        data = img.convert("RGBA").tobytes("raw", "BGRA")
        self.mm.seek(0)
        for _ in range(self.pages):
            self.mm.write(data)

    def close(self):
        self.mm.close()
        os.close(self.fb)


def keys():
    """Yields (code, value) for key presses/repeats and D-pad moves."""
    with open("/dev/input/event1", "rb") as f:
        while True:
            _, _, etype, code, value = struct.unpack("llHHi", f.read(24))
            if etype in (1, 3) and value != 0:
                yield code, value


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--png":
        draw_main().save(sys.argv[2])
        return
    scr = Screen()
    try:
        scr.show(draw_main())
        mode, rows, page, pages = "main", [], 0, 1
        for code, value in keys():
            if code == KEY_MENU or (code == KEY_B and mode == "main"):
                break
            if mode == "main" and code == KEY_A:
                scr.show(draw_message("Calculando..."))
                rows, page = roms_usage(), 0
                img, pages = draw_roms(rows, page)
                scr.show(img)
                mode = "roms"
            elif mode == "roms" and code == KEY_B:
                scr.show(draw_main())
                mode = "main"
            elif mode == "roms" and code == 16:  # D-pad left/right (ABS_HAT0X)
                page = (page + (1 if value > 0 else -1)) % pages
                img, pages = draw_roms(rows, page)
                scr.show(img)
    finally:
        scr.close()


if __name__ == "__main__":
    main()
