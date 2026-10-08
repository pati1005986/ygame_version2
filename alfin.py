"""
Animación en pygame a partir de un dibujo a carbón  (versión carboncillo).

Igual que la original: pixelado con detalle, lupa, "boil" de línea a mano,
granulado y escala de grises estricta.  Novedades:

  * El carbón se deposita sobre un PAPEL con dientes (textura fija): en los
    medios tonos el pigmento "salta" los huecos del papel, como en un
    carboncillo real; en las sombras profundas el negro se asienta lleno.
  * Matices: capa difuminada (dedo / difumino) mezclada con el trazo seco,
    así hay degradados suaves junto a líneas duras.
  * Intro nueva: el papel está en blanco y el dibujo SE VA DIBUJANDO por
    pasadas de trazos diagonales; primero los grises claros y luego se
    cargan las sombras.
  * El papel no tiembla; solo el dibujo respira/"hierve" encima de él.

Requisitos:  pip install pygame numpy pillow
Ejecutar:    python alfin.py   (con dibujo.png en la misma carpeta)
             python alfin.py ruta/otra_imagen.png

Controles
  Mouse ........ una "lupa" revela el detalle fino bajo el cursor
                 (si lo dejas quieto, la lupa pasea sola)
  ← / →  ....... tamaño del píxel (más grande / más pequeño)
  ↑ / ↓  ....... niveles de gris (2 a 32)
  G ............ granulado on/off
  T ............ textura de papel (dientes) on/off
  D ............ tramado (dithering) on/off
  P ............ papel tonalidad: gris estricto / crema
  R ............ repetir la intro (dibujándose)
  ESPACIO ...... pausa
  S ............ guardar captura PNG
  H ............ mostrar/ocultar ayuda
  ESC .......... salir
"""
import os
import sys
import math
import numpy as np
from PIL import Image, ImageFilter

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

PIXEL_SIZES = [2, 3, 4, 5, 6, 8, 10]
BAYER4 = np.array([[0, 8, 2, 10],
                   [12, 4, 14, 6],
                   [3, 11, 1, 9],
                   [15, 7, 13, 5]], dtype=np.float32) / 16.0


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def normalizar(a):
    """Lleva un campo de ruido a ~[0,1] con media 0.5."""
    z = (a - a.mean()) / (a.std() + 1e-6)
    return np.clip(0.5 + 0.22 * z, 0, 1).astype(np.float32)


def campo_ruido(rng, w, h, sw, sh, resample=Image.BICUBIC):
    """Ruido aleatorio de (sw, sh) celdas reescalado a (w, h)."""
    r = rng.random((max(sh, 1), max(sw, 1))).astype(np.float32)
    im = Image.fromarray((r * 255).astype(np.uint8), "L").resize((w, h), resample)
    return np.asarray(im, dtype=np.float32) / 255.0


class Dibujo:
    """Prepara las capas del dibujo y del papel para un tamaño de píxel."""

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
        self.build(3)

    def build(self, px):
        self.px = px
        w, h = self.win_w // px, self.win_h // px
        self.w, self.h = w, h
        rng = np.random.default_rng(11)    # papel y trazos: fijos entre rebuilds

        # --- pigmento (oscuridad = 1 - luminosidad) en tres versiones ---
        fine = self.base.resize((w, h), Image.BOX)
        coarse = self.base.resize((max(w // 3, 1), max(h // 3, 1)), Image.BOX)
        coarse = coarse.resize((w, h), Image.NEAREST)
        # difumino: el carbón frotado con el dedo
        smudge = self.base.filter(ImageFilter.GaussianBlur(max(px * 1.6, 3)))
        smudge = smudge.resize((w, h), Image.BOX)
        self.fine = 1.0 - np.asarray(fine, dtype=np.float32) / 255.0
        self.smudge = 1.0 - np.asarray(smudge, dtype=np.float32) / 255.0
        coarse = 1.0 - np.asarray(coarse, dtype=np.float32) / 255.0
        # lejos de la lupa: bloques gruesos suavizados con el difuminado
        self.coarse = 0.55 * coarse + 0.45 * self.smudge

        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        self.xx, self.yy = xx, yy
        self.bayer = np.tile(BAYER4, (h // 4 + 1, w // 4 + 1))[:h, :w]

        # --- papel con dientes: puntitos + fibras verticales + ondulación ---
        puntos = normalizar(rng.random((h, w)).astype(np.float32))
        puntos = normalizar(np.asarray(
            Image.fromarray((puntos * 255).astype(np.uint8), "L")
            .filter(ImageFilter.GaussianBlur(1.0)), dtype=np.float32))
        fibras = normalizar(campo_ruido(rng, w, h, w, max(h // 7, 2)))
        manchas = normalizar(campo_ruido(rng, w, h, max(w // 14, 2), max(h // 14, 2)))
        self.tooth = np.clip(0.40 * puntos + 0.40 * fibras + 0.20 * manchas, 0, 1)
        self.tooth = normalizar(self.tooth)
        self.tooth = np.clip((self.tooth - 0.5) * 1.2 + 0.5, 0, 1).astype(np.float32)

        # --- orden en que se dibuja cada zona (intro): pasadas diagonales ---
        region = campo_ruido(rng, w, h, max(w // 10, 3), max(h // 10, 3))
        ruido_fino = campo_ruido(rng, w, h, max(w // 3, 3), max(h // 3, 3))
        hatch = 0.5 + 0.5 * np.sin((xx * 0.9 + yy * 1.0) * 0.45 + ruido_fino * 5.0)
        self.order = (0.6 * region + 0.4 * hatch).astype(np.float32)

        # --- viñeta ---
        d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
        self.vignette = (1.0 - 0.30 * smoothstep((d - 0.55) / 0.9)).astype(np.float32)
        self.rows = np.arange(h)[:, None]
        self.cols = np.arange(w)[None, :]


def render(d, t, mouse, levels, grain_on, dither_on, intro, paper_on=True,
           crema=False):
    """Devuelve un array uint8 (h, w) en escala de grises
    (o (h, w, 3) si crema=True)."""
    w, h = d.w, d.h

    # 1) lupa: el detalle fino (trazo seco) aparece alrededor de (mx, my)
    mx, my = mouse
    radius = min(w, h) * 0.22
    dist = np.sqrt((d.xx - mx) ** 2 + (d.yy - my) ** 2)
    lens = smoothstep((radius - dist) / (radius * 0.45))
    # dentro de la lupa: trazo fino + un poco de difumino para dar matiz
    nitido = 0.82 * d.fine + 0.18 * d.smudge
    pig = d.coarse * (1 - lens) + nitido * lens

    # 2) "boil": temblor de línea a mano, a 8 fps (solo el dibujo, no el papel)
    step = int(t * 8)
    rng = np.random.default_rng(step)
    amp = 0.9
    shift = np.rint(np.sin(d.yy[:, :1] * 0.23 + step * 1.7) * amp +
                    rng.uniform(-0.6, 0.6, (h, 1))).astype(int)
    cols = (d.cols + shift) % w
    pig = pig[d.rows, cols]

    # 3) respiración de presión + parpadeo
    pig = pig * (1.0 + 0.035 * math.sin(t * 1.3) + rng.uniform(-0.012, 0.012))
    pig = np.clip(pig * 1.04, 0, 1)

    # 4) intro: el dibujo se construye por pasadas (claros primero, sombras después)
    if intro < 1.0:
        s = smoothstep((intro * 1.7 - 0.8 * d.order - 0.30 * pig - 0.1) / 0.35)
        pig = pig * s

    # 5) el carbón se agarra a los dientes del papel (medios tonos saltan)
    if paper_on:
        salto = (d.tooth ** 1.6) * (1.0 - pig) ** 1.2 * 0.55
        pig = np.clip((pig - salto * 0.60) * 1.05 + salto * 0.05, 0, 1)

    # 6) granulado de película/carbón (más presente en medios tonos)
    if grain_on:
        mid = 0.45 + 0.55 * (4 * pig * (1 - pig))
        pig = pig + np.random.normal(0, 0.022, (h, w)).astype(np.float32) * mid
        pig = np.clip(pig, 0, 1)

    # 7) del pigmento a la luminosidad: papel claro con dientes + carbón
    papel = 0.95 - (0.07 * d.tooth if paper_on else 0.0)
    img = papel * (1.0 - 0.94 * pig)

    if grain_on:
        dust = np.random.random((h, w))
        img = np.where(dust > 0.9990, 0.97, img)    # motas de borrador
        img = np.where(dust < 0.0008, 0.05, img)    # migas de carbón

    # barra de barrido de luz
    band_pos = (t * 0.12 % 1.4 - 0.2) * h
    img = img + 0.05 * np.exp(-((d.yy[:, :1] - band_pos) / (h * 0.035)) ** 2)
    img = np.clip(img * d.vignette, 0, 1)

    # 8) cuantización a pocos grises, con tramado Bayer opcional
    n = levels - 1
    if dither_on:
        q = np.floor(img * n + 0.5 + (d.bayer - 0.5) * 0.6)
    else:
        q = np.floor(img * n + 0.5)
    q = np.clip(q, 0, n) / n

    if crema:   # papel cálido: mismas luces, tinte suave
        tinte = np.array([1.0, 0.95, 0.82], dtype=np.float32)
        return (np.clip(q[:, :, None] * tinte, 0, 1) * 255).astype(np.uint8)
    return (q * 255).astype(np.uint8)


def main():
    import pygame

    if not os.path.isfile(IMG_PATH):
        raise FileNotFoundError(f"No se encontró la imagen del dibujo: {IMG_PATH}")

    pygame.init()
    probe = Image.open(IMG_PATH)
    iw, ih = probe.size
    scale = min(1.0, 980 / ih)
    win_w, win_h = int(iw * scale) // 12 * 12, int(ih * scale) // 12 * 12
    screen = pygame.display.set_mode((win_w, win_h))
    pygame.display.set_caption("Dibujo en movimiento - carboncillo")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 22)

    d = Dibujo(IMG_PATH, win_w, win_h)
    px_idx, levels = 1, 12
    d.build(PIXEL_SIZES[px_idx])
    grain_on, dither_on, paper_on = True, True, True
    show_help, paused, crema = True, False, False
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
                elif e.key == pygame.K_t:
                    paper_on = not paper_on
                elif e.key == pygame.K_d:
                    dither_on = not dither_on
                elif e.key == pygame.K_p:
                    crema = not crema
                elif e.key == pygame.K_h:
                    show_help = not show_help
                elif e.key == pygame.K_r:
                    intro = 0.0
                elif e.key == pygame.K_UP:
                    levels = min(32, levels + 1)
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
            intro = min(1.0, intro + dt / 9.0)   # ~9 s dibujándose

        # lupa automática si el mouse está quieto
        if t - last_move > 3.0:
            mouse_win = (win_w * (0.5 + 0.28 * math.sin(t * 0.55)),
                         win_h * (0.38 + 0.22 * math.sin(t * 0.83 + 1.0)))
        mouse = (mouse_win[0] / d.px, mouse_win[1] / d.px)

        out = render(d, t, mouse, levels, grain_on, dither_on, intro,
                     paper_on, crema)
        if out.ndim == 2:
            rgb = np.repeat(out.T[:, :, None], 3, axis=2)    # (w, h, 3), R=G=B
        else:
            rgb = np.ascontiguousarray(out.transpose(1, 0, 2))
        small = pygame.surfarray.make_surface(rgb)
        screen.blit(pygame.transform.scale(small, (win_w, win_h)), (0, 0))

        if show_help:
            lines = [f"pixel {d.px}px  grises {levels}  grano {'on' if grain_on else 'off'}"
                     f"  papel {'on' if paper_on else 'off'}"
                     f"  tramado {'on' if dither_on else 'off'}",
                     "←→ pixel  ↑↓ grises  G grano  T papel  D tramado  P tono  "
                     "R intro  S captura  H ayuda"]
            for i, txt in enumerate(lines):
                s = font.render(txt, True, (200, 200, 200), (20, 20, 20))
                screen.blit(s, (8, 8 + i * 20))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()