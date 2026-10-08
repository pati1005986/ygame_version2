"""
Animación en pygame a partir de un dibujo a carbón.
Pixelado con detalle, granulado y escala de grises estricta.

Requisitos:  pip install pygame numpy pillow
Ejecutar:    python animacion_dibujo.py   (con dibujo.png en la misma carpeta)

Controles
  Mouse ........ una "lupa" revela el detalle fino bajo el cursor
                 (si lo dejas quieto, la lupa pasea sola)
  ← / →  ....... tamaño del píxel (más grande / más pequeño)
  ↑ / ↓  ....... niveles de gris (2 a 16)
  G ............ activar/desactivar granulado
  D ............ activar/desactivar tramado (dithering)
  R ............ repetir la intro (estática -> dibujo)
  ESPACIO ...... pausa
  S ............ guardar captura PNG
  H ............ mostrar/ocultar ayuda
  ESC .......... salir
"""
import os
import sys
import math
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))

candidatos = []
if len(sys.argv) > 1:
    candidatos.append(sys.argv[1])
candidatos.extend([
    os.path.join(HERE, "dibujo.png"),
    os.path.join(HERE, "assets", "dibujo.png"),
])

IMG_PATH = next(
    (ruta for ruta in candidatos if ruta and os.path.isfile(ruta)),
    os.path.join(HERE, "assets", "dibujo.png"),
)

if not os.path.isfile(IMG_PATH):
    raise FileNotFoundError(f"No se encontró la imagen del dibujo: {IMG_PATH}")

PIXEL_SIZES = [2, 3, 4, 5, 6, 8, 10]
BAYER4 = np.array([[0, 8, 2, 10],
                   [12, 4, 14, 6],
                   [3, 11, 1, 9],
                   [15, 7, 13, 5]], dtype=np.float32) / 16.0


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


class Dibujo:
    """Prepara las versiones fina y gruesa del dibujo para un tamaño de píxel."""

    def __init__(self, path, win_w, win_h):
        gray = Image.open(path).convert("L")
        gray = gray.resize((win_w, win_h), Image.LANCZOS)
        a = np.asarray(gray, dtype=np.float32) / 255.0
        lo, hi = np.percentile(a, 1), np.percentile(a, 99)
        a = np.clip((a - lo) / max(hi - lo, 1e-3), 0, 1)
        a = a ** 1.3                       # un poco más de contraste en sombras
        self.base = Image.fromarray((a * 255).astype(np.uint8), "L")
        self.win_w, self.win_h = win_w, win_h
        self.rng = np.random.default_rng(7)
        self.build(4)

    def build(self, px):
        self.px = px
        w, h = self.win_w // px, self.win_h // px
        self.w, self.h = w, h
        fine = self.base.resize((w, h), Image.BOX)
        coarse = self.base.resize((max(w // 3, 1), max(h // 3, 1)), Image.BOX)
        coarse = coarse.resize((w, h), Image.NEAREST)
        self.fine = np.asarray(fine, dtype=np.float32) / 255.0
        self.coarse = np.asarray(coarse, dtype=np.float32) / 255.0

        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        self.xx, self.yy = xx, yy
        self.bayer = np.tile(BAYER4, (h // 4 + 1, w // 4 + 1))[:h, :w]
        self.reveal_rand = self.rng.random((h, w)).astype(np.float32)
        # viñeta
        d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
        self.vignette = (1.0 - 0.35 * smoothstep((d - 0.55) / 0.9)).astype(np.float32)
        # mapas de ondulación tipo "dibujo vivo" (boil): se cambian a pocos fps
        self.rows = np.arange(h)[:, None]
        self.cols = np.arange(w)[None, :]


def render(d, t, mouse, levels, grain_on, dither_on, intro):
    """Devuelve un array uint8 (h, w) en escala de grises."""
    w, h = d.w, d.h

    # 1) lupa: el detalle fino aparece alrededor de (mx, my)
    mx, my = mouse
    radius = min(w, h) * 0.22
    dist = np.sqrt((d.xx - mx) ** 2 + (d.yy - my) ** 2)
    lens = smoothstep((radius - dist) / (radius * 0.45))
    img = d.coarse * (1 - lens) + d.fine * lens

    # 2) "boil": temblor de línea a mano, a 8 fps
    step = int(t * 8)
    rng = np.random.default_rng(step)
    amp = 0.9
    shift = np.rint(np.sin(d.yy[:, :1] * 0.23 + step * 1.7) * amp +
                    rng.uniform(-0.6, 0.6, (h, 1))).astype(int)
    cols = (d.cols + shift) % w
    img = img[d.rows, cols]

    # 3) respiración de luz + parpadeo + barra de barrido
    light = 1.0 + 0.035 * math.sin(t * 1.3) + rng.uniform(-0.012, 0.012)
    band_pos = (t * 0.12 % 1.4 - 0.2) * h
    band = 0.07 * np.exp(-((d.yy[:, :1] - band_pos) / (h * 0.035)) ** 2)
    img = img * light + band

    # 4) granulado de película (más presente en medios tonos)
    if grain_on:
        mid = 0.55 + 0.45 * (4 * img * (1 - img))
        g = np.random.normal(0, 0.06, (h, w)).astype(np.float32) * mid
        img = img + g
        dust = np.random.random((h, w))
        img = np.where(dust > 0.9975, 1.0, img)
        img = np.where(dust < 0.0020, 0.0, img)

    img = np.clip(img * d.vignette, 0, 1)

    # 5) intro: estática de TV que se resuelve en el dibujo
    if intro < 1.0:
        static = np.random.random((h, w)).astype(np.float32) * 0.8
        shown = d.reveal_rand < (intro * 1.15)
        img = np.where(shown, img, static)

    # 6) cuantización a pocos grises, con tramado Bayer opcional
    n = levels - 1
    if dither_on:
        q = np.floor(img * n + 0.5 + (d.bayer - 0.5) * 0.6)
    else:
        q = np.floor(img * n + 0.5)
    q = np.clip(q, 0, n) / n
    return (q * 255).astype(np.uint8)


def main():
    import pygame

    pygame.init()
    probe = Image.open(IMG_PATH)
    iw, ih = probe.size
    scale = min(1.0, 980 / ih)
    win_w, win_h = int(iw * scale) // 12 * 12, int(ih * scale) // 12 * 12
    screen = pygame.display.set_mode((win_w, win_h))
    pygame.display.set_caption("Dibujo en movimiento")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 22)

    d = Dibujo(IMG_PATH, win_w, win_h)
    px_idx, levels = 2, 6
    d.build(PIXEL_SIZES[px_idx])
    grain_on, dither_on, show_help, paused = True, True, True, False
    t, intro = 0.0, 0.0
    mouse_win = (win_w // 2, win_h // 3)
    last_move = -10.0
    shot = 0

    running = True
    while running:
        dt = clock.tick(30) / 1000.0
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.MOUSEMOTION:
                mouse_win = e.pos
                last_move = t
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
                elif e.key == pygame.K_SPACE:
                    paused = not paused
                elif e.key == pygame.K_g:
                    grain_on = not grain_on
                elif e.key == pygame.K_d:
                    dither_on = not dither_on
                elif e.key == pygame.K_h:
                    show_help = not show_help
                elif e.key == pygame.K_r:
                    intro = 0.0
                elif e.key == pygame.K_UP:
                    levels = min(16, levels + 1)
                elif e.key == pygame.K_DOWN:
                    levels = max(2, levels - 1)
                elif e.key == pygame.K_RIGHT:   # píxel más fino
                    px_idx = max(0, px_idx - 1)
                    d.build(PIXEL_SIZES[px_idx])
                elif e.key == pygame.K_LEFT:    # píxel más grande
                    px_idx = min(len(PIXEL_SIZES) - 1, px_idx + 1)
                    d.build(PIXEL_SIZES[px_idx])
                elif e.key == pygame.K_s:
                    pygame.image.save(screen, os.path.join(HERE, f"captura_{shot:02d}.png"))
                    shot += 1

        if not paused:
            t += dt
            intro = min(1.0, intro + dt / 3.5)

        # lupa automática si el mouse está quieto
        if t - last_move > 3.0:
            mouse_win = (win_w * (0.5 + 0.28 * math.sin(t * 0.55)),
                         win_h * (0.38 + 0.22 * math.sin(t * 0.83 + 1.0)))
        mouse = (mouse_win[0] / d.px, mouse_win[1] / d.px)

        gray = render(d, t, mouse, levels, grain_on, dither_on, intro)
        rgb = np.repeat(gray.T[:, :, None], 3, axis=2)       # (w, h, 3), R=G=B
        small = pygame.surfarray.make_surface(rgb)
        screen.blit(pygame.transform.scale(small, (win_w, win_h)), (0, 0))

        if show_help:
            lines = [f"pixel {d.px}px  grises {levels}  grano {'on' if grain_on else 'off'}"
                     f"  tramado {'on' if dither_on else 'off'}",
                     "←→ pixel  ↑↓ grises  G grano  D tramado  R intro  S captura  H ayuda"]
            for i, txt in enumerate(lines):
                s = font.render(txt, True, (200, 200, 200), (20, 20, 20))
                screen.blit(s, (8, 8 + i * 20))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()