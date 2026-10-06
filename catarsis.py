"""
LAS VOCES  -  el despertar
--------------------------
Todo está dibujado por código (no usa ninguna imagen): el chico de ojos
enormes, el pelo erizado, el suéter a rayas, la bata y las voces que lo rodean.

La escena ya no es una crisis: empieza con el chico DORMIDO, rodeado de las
voces que murmuran (ojos que lo vigilan, bocas cosidas que se abren, cintas de
susurro). Poco a poco su cuerpo se mueve, los párpados aletean, abre los ojos,
las voces se quedan dormidas y se deshacen en burbujas, el cielo pasa de noche
a amanecer, bosteza y sonríe.

Además lleva grano de película animado, polvo y rayones sobre toda la imagen.

Requisitos:  pip install pygame

Controles:
  ESPACIO  -> adelantar el despertar
  G        -> activar / quitar el grano
  R        -> reiniciar
  M        -> silenciar / activar sonido
  ESC      -> salir

``AnimacionCatarsis`` permite reutilizar la escena como pantalla de transición
sin crear otra ventana ni interceptar los eventos del juego anfitrión.
"""
import math
import os
import random
import sys
from array import array

import pygame

# ------------------------------------------------------------------ config
W, H = 640, 900
FPS = 60
T_DESPIERTA = 5.0          # segundo en que empieza a abrir los ojos
T_REINICIO = 28.0          # segundo en que la escena se reinicia (en main)
TAU = math.tau

INK = (14, 14, 20)
PAPEL = (246, 242, 236)
PIEL = (253, 251, 248)
AZUL = (30, 168, 226)
NOCHE = (18, 50, 128)
ROSA = (236, 120, 136)
CALIDO = (255, 243, 214)


# ------------------------------------------------------------------ utilidades
def clamp01(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def lerp(a, b, t):
    return a + (b - a) * t


def smooth(a, b, x):
    t = clamp01((x - a) / (b - a))
    return t * t * (3 - 2 * t)


def bump(t, a, b):
    """Campana suave 0 -> 1 -> 0 entre a y b."""
    if t <= a or t >= b:
        return 0.0
    return math.sin(math.pi * (t - a) / (b - a)) ** 2


def mix(c1, c2, t):
    return tuple(int(lerp(c1[i], c2[i], t)) for i in range(3))


def tline(s, col, p0, p1, w):
    p0 = (int(p0[0]), int(p0[1]))
    p1 = (int(p1[0]), int(p1[1]))
    pygame.draw.line(s, col, p0, p1, max(1, int(w)))
    if w > 2:
        r = int(w) // 2
        pygame.draw.circle(s, col, p0, r)
        pygame.draw.circle(s, col, p1, r)


def tpoly(s, col, pts, w):
    for a, b in zip(pts, pts[1:]):
        tline(s, col, a, b, w)


def poli(s, relleno, pts, w):
    """Polígono relleno con contorno de tinta grueso y esquinas redondeadas."""
    pygame.draw.polygon(s, relleno, pts)
    tpoly(s, INK, list(pts) + [pts[0]], w)


def arco(s, col, cx, cy, rx, ry, a0, a1, w):
    """Arco como polilínea (convención de pygame: ángulos antihorarios)."""
    n = 14
    pts = [(cx + rx * math.cos(a0 + (a1 - a0) * i / n),
            cy - ry * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
    tpoly(s, col, pts, w)


def ruido(i, tb):
    """Ruido determinista en [-1, 1] (para el 'boil' del trazo)."""
    x = math.sin(i * 12.9898 + tb * 78.233) * 43758.5453
    return (x - math.floor(x)) * 2 - 1


def blob_points(cx, cy, rx, ry, rot, seed, t, wob):
    pts = []
    n = 30
    tb = int(t * 10)
    amp = 0.6 + 0.35 * wob
    c, sn = math.cos(rot), math.sin(rot)
    for i in range(n):
        a = i / n * TAU
        r = 1 + 0.07 * math.sin(3 * a + seed) + 0.05 * math.sin(5 * a + seed * 2 + t * wob)
        x = math.cos(a) * rx * r + ruido(i + seed * 7, tb) * amp
        y = math.sin(a) * ry * r + ruido(i + 50 + seed * 7, tb) * amp
        pts.append((cx + x * c - y * sn, cy + x * sn + y * c))
    return pts


# ------------------------------------------------------------------ línea de tiempo
class Estado:
    """Todo lo que cambia con el despertar, derivado del tiempo."""
    __slots__ = ("sueno", "ojos", "alba", "bostezo", "sonrisa", "enfoque", "voces")


def estado(t):
    e = Estado()
    e.sueno = 1.0 - smooth(4.6, 11.0, t)                 # 1 dormido  ->  0 despierto
    aleteo = 0.16 * bump(t, 2.4, 3.3) + 0.26 * bump(t, 3.7, 4.8)
    ojos = max(smooth(5.0, 7.6, t), aleteo)               # apertura de los párpados
    e.ojos = ojos * (1.0 - 0.9 * bump(t, 8.2, 8.8))       # primer parpadeo lento
    e.alba = smooth(5.2, 13.0, t)                         # noche -> amanecer
    e.bostezo = bump(t, 9.8, 12.4)
    e.sonrisa = smooth(12.4, 16.0, t)
    e.enfoque = smooth(5.8, 9.5, t)                       # las pupilas se enfocan
    e.voces = smooth(0.0, 3.0, t) * (1.0 - smooth(5.2, 10.5, t))
    return e


# ------------------------------------------------------------------ fondo
def crear_trazos():
    """Trazos de marcador sobre el fondo (se crean una sola vez)."""
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    rnd = random.Random(3)
    for _ in range(300):
        x, y = rnd.randint(0, W), rnd.randint(0, H)
        l = rnd.randint(40, 150)
        if rnd.random() < 0.5:
            col = (255, 255, 255, rnd.randint(10, 28))
        else:
            col = (0, 40, 90, rnd.randint(10, 26))
        pygame.draw.line(s, col, (x, y), (x + l * 0.6, y + l * 0.8), rnd.randint(3, 10))
    return s


def crear_vineta():
    n = 96
    v = pygame.Surface((n, n), pygame.SRCALPHA)
    c = n / 2
    for y in range(n):
        for x in range(n):
            d = math.hypot(x - c, y - c) / c
            a = clamp01((d - 0.45) / 0.7)
            v.set_at((x, y), (0, 0, 0, int(255 * a)))
    return pygame.transform.smoothscale(v, (W, H))


def crear_sol():
    """Resplandor cálido del amanecer (gradiente radial)."""
    n = 64
    v = pygame.Surface((n, n), pygame.SRCALPHA)
    c = n / 2
    for y in range(n):
        for x in range(n):
            d = math.hypot(x - c, y - c) / c
            a = clamp01(1 - d) ** 2
            v.set_at((x, y), (255, 236, 190, int(255 * a)))
    return pygame.transform.smoothscale(v, (820, 820))


def crear_haces():
    """Haces de luz de la mañana que entran en diagonal."""
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    for x0, ancho, a in ((330, 70, 50), (470, 120, 36), (600, 60, 56), (200, 40, 30), (80, 30, 22)):
        pts = [(x0, -20), (x0 + ancho, -20), (x0 + ancho - 560, H + 20), (x0 - 560, H + 20)]
        pygame.draw.polygon(s, (255, 240, 200, a), pts)
    return s


TRAZOS = crear_trazos()
VINETA = crear_vineta()
SOL = crear_sol()
HACES = crear_haces()


def dibujar_espiral(s):
    n = 14
    for i in range(n):
        x = 38 + i * (W - 76) / (n - 1)
        pygame.draw.ellipse(s, (60, 60, 66), (x - 7, 12, 14, 9))          # agujero
        pygame.draw.rect(s, (28, 28, 34), (x - 5, 2, 10, 24), border_radius=5)
        pygame.draw.rect(s, (150, 150, 160), (x - 2, 5, 3, 16), border_radius=2)


# ------------------------------------------------------------------ grano de película
class Grano:
    """Grano analógico animado: varias texturas de ruido que se alternan."""

    def __init__(self):
        self.finos = [self._tile(W // 2, H // 2) for _ in range(6)]
        self.gruesos = [self._tile(W // 4, H // 4) for _ in range(4)]
        self.i = 0
        self.j = 0

    @staticmethod
    def _tile(w, h):
        raw = os.urandom(w * h)
        buf = bytearray(w * h * 3)
        buf[0::3] = raw
        buf[1::3] = raw
        buf[2::3] = raw
        surf = pygame.image.frombuffer(bytes(buf), (w, h), "RGB")
        try:
            return surf.convert()
        except pygame.error:
            return surf.copy()

    def aplicar(self, destino, fino, grueso):
        self.i = (self.i + random.randint(1, len(self.finos) - 1)) % len(self.finos)
        self.j = (self.j + random.randint(1, len(self.gruesos) - 1)) % len(self.gruesos)
        a = pygame.transform.scale(self.finos[self.i], (W, H))
        a.set_alpha(int(fino))
        destino.blit(a, (0, 0))
        b = pygame.transform.scale(self.gruesos[self.j], (W, H))
        b.set_alpha(int(grueso))
        destino.blit(b, (0, 0))


_CACHE = {}


def grano():
    if "grano" not in _CACHE:
        _CACHE["grano"] = Grano()
    return _CACHE["grano"]


def velo(destino, color, alpha):
    """Capa de color uniforme con transparencia."""
    if alpha < 1:
        return
    v = _CACHE.get("velo")
    if v is None:
        v = _CACHE["velo"] = pygame.Surface((W, H))
    v.fill(color)
    v.set_alpha(int(min(255, alpha)))
    destino.blit(v, (0, 0))


def polvo(destino):
    """Rayones verticales y motas de polvo de película vieja."""
    if random.random() < 0.10:
        x = random.randint(0, W)
        y = random.randint(0, H - 220)
        pygame.draw.line(destino, (226, 226, 216), (x, y),
                         (x + random.randint(-2, 2), y + random.randint(60, 220)), 1)
    for _ in range(5):
        pos = (random.randint(0, W - 1), random.randint(0, H - 1))
        col = (236, 236, 226) if random.random() < 0.55 else (18, 18, 24)
        pygame.draw.circle(destino, col, pos, random.choice((1, 1, 2)))


# ------------------------------------------------------------------ las voces (entes)
def boca_ente(s, cx, cy, w, h, ab, seed):
    """Boca con dientes y lengua; cerrada, es una costura de puntadas."""
    w = max(16, int(w))
    h = max(14, int(h))
    gap = h * 0.92 * ab
    if gap < 5:
        n = 12
        pts = [(cx + (i / n * 2 - 1) * w * 0.5, cy + math.sin(i * 1.3 + seed) * 2.0) for i in range(n + 1)]
        tpoly(s, INK, pts, 6)
        for i in range(1, n, 2):
            tline(s, INK, (pts[i][0], cy - 9), (pts[i][0] + 1, cy + 9), 3)
        return
    sup, inf = [], []
    for q in range(17):
        u = q / 16 * 2 - 1
        f = max(0.0, 1 - u * u) ** 0.6
        sup.append((cx + u * w / 2, cy - gap * 0.5 * f))
        inf.append((cx + u * w / 2, cy + gap * 0.5 * f))
    contorno = sup + inf[::-1]
    pygame.draw.polygon(s, INK, contorno)
    if gap > 12:
        lg = pygame.Rect(0, 0, int(w * 0.46), int(gap * 0.38))
        lg.center = (int(cx), int(cy + gap * 0.26))
        pygame.draw.ellipse(s, ROSA, lg)
    th = int(min(gap * 0.42, 15))
    if th >= 4:
        for i in range(-2, 3):
            x = cx + i * w * 0.17
            yy = cy - gap * 0.5 * max(0.0, 1 - (i * 0.34) ** 2) ** 0.6
            pygame.draw.polygon(s, PAPEL, [(x - 6, yy), (x + 6, yy), (x + 3, yy + th), (x - 3, yy + th)])
        for i in range(-1, 2):
            x = cx + (i + 0.5) * w * 0.17 * 1.3
            yy = cy + gap * 0.5 * max(0.0, 1 - ((i + 0.5) * 0.44) ** 2) ** 0.6
            pygame.draw.polygon(s, PAPEL, [(x - 5, yy), (x + 5, yy), (x + 2, yy - th * 0.8), (x - 2, yy - th * 0.8)])
    tpoly(s, INK, contorno + [contorno[0]], 5)


def ojo_ente(s, x, y, R, ux, uy, cierre, papel):
    """Ojo que vigila al chico; el párpado cae cuando la voz se duerme."""
    R = max(7, int(R))
    x, y = int(x), int(y)
    c = clamp01(cierre)
    pygame.draw.circle(s, (255, 255, 255), (x, y), R)
    pr = R * 0.56
    px, py = x + ux * R * 0.3, y + uy * R * 0.3
    pygame.draw.circle(s, INK, (int(px), int(py)), int(pr))
    pygame.draw.circle(s, (255, 255, 255), (int(px - pr * 0.35), int(py - pr * 0.35)), max(2, int(pr * 0.24)))
    if c > 0.02:
        yl = y - R + 2 * R * c
        borde = [(x + u * R, yl + R * 0.16 * c * (1 - u * u)) for u in [1 - i / 6 for i in range(13)]]
        s.set_clip(pygame.Rect(x - R - 1, y - R - 1, 2 * R + 2, 2 * R + 2))
        pygame.draw.polygon(s, papel, [(x + R + 4, y - R - 4), (x - R - 4, y - R - 4)] + borde[::-1])
        s.set_clip(None)
        tpoly(s, INK, borde, 4)
    pygame.draw.circle(s, INK, (x, y), R, 5)
    arco(s, INK, x, y - 1, R + 4, R + 4, 0.7, 2.45, 6)            # ceja pesada


def tubo(s, cx, cy, largo, vertical, t, seed, ancho, d):
    """Cinta ondulada de 'voz' con borde de tinta (como en el dibujo)."""
    pts = []
    n = max(4, int(largo / 6))
    for i in range(n + 1):
        u = (i / n - 0.5) * largo
        amp = 5 + 9 * d
        o = math.sin(i * 0.7 + seed + t * (1.6 + 5 * d)) * amp
        pts.append((cx + o, cy + u) if vertical else (cx + u, cy + o))
    tpoly(s, INK, pts, ancho + 11)
    tpoly(s, PAPEL, pts, ancho)
    tpoly(s, (150, 180, 214), pts, max(2, ancho // 3))              # veta interior
    for p in (pts[0], pts[-1]):
        pygame.draw.circle(s, INK, (int(p[0]), int(p[1])), ancho // 2 + 5)
        pygame.draw.circle(s, PAPEL, (int(p[0]), int(p[1])), ancho // 2)


def ondas_voz(s, px, py, largo, ux, uy, t, seed, fuerza):
    """Arcos de sonido que viajan de la boca hacia el chico."""
    ang = -math.atan2(uy, ux)
    for q in range(3):
        p = (t * 0.55 + q / 3 + seed * 0.13) % 1.0
        r = largo * 0.95 + p * 70
        w = 2 + 5 * (1 - p) * fuerza
        if w < 2.2:
            continue
        cx, cy = px, py
        pts = [(cx + r * math.cos(ang + a), cy - r * math.sin(ang + a))
               for a in [(-0.42 + 0.84 * i / 9) * (1 - 0.3 * p) for i in range(10)]]
        tpoly(s, INK, pts, w + 6)
        tpoly(s, PAPEL, pts, w)


class Ente:
    """Una voz: un cuerpo de tinta con ojos, bocas cosidas o cintas de susurro."""

    def __init__(self, x, y, rx, ry, rot, items, llega, se_va, seed):
        self.x, self.y, self.rx, self.ry = x, y, rx, ry
        self.rot, self.items, self.llega, self.se_va, self.seed = rot, items, llega, se_va, seed
        self.acum = 0.0

    def rayado(self, s, px, py, rx, ry):
        """Sombreado a pluma en el borde inferior izquierdo del cuerpo."""
        c, sn = math.cos(self.rot), math.sin(self.rot)
        n = 9
        for i in range(n):
            a = math.radians(95 + 100 * i / (n - 1))
            L = 0.16 + 0.16 * (0.5 + 0.5 * math.sin(i * 2.1 + self.seed))
            p = []
            for rr in (0.9, 0.9 - L):
                x = math.cos(a) * rx * rr - (0.9 - rr) * rx * 0.25
                y = math.sin(a) * ry * rr
                p.append((px + x * c - y * sn, py + x * sn + y * c))
            tline(s, INK, p[0], p[1], 3)

    def dibujar(self, s, t, e, dt, mundo, bg):
        entra = smooth(self.llega, self.llega + 1.0, t)
        sale = smooth(self.se_va, self.se_va + 1.7, t)
        k = entra * (1 - sale)
        if k < 0.02:
            return
        k *= 1 + 0.035 * math.sin(t * 1.9 + self.seed)
        px = self.x + 6 * math.sin(t * 0.7 + self.seed)
        py = self.y + 7 * math.sin(t * 0.55 + self.seed * 1.7) - 46 * sale * sale
        rx, ry = self.rx * k, self.ry * k
        fuerza = e.sueno
        largo, corto = max(rx, ry), min(rx, ry)

        # al quedarse dormida, la voz se deshace en burbujas
        if 0.03 < sale < 0.97:
            self.acum += dt * 34 * (1 - sale * 0.5)
            while self.acum >= 1:
                self.acum -= 1
                mundo.emitir(px, py, rx, ry, self.rot)

        dx, dy = W / 2 - px, 450 - py
        dist = math.hypot(dx, dy) or 1.0
        ux, uy = dx / dist, dy / dist
        papel = mix(PAPEL, CALIDO, sale)

        solo_ojos = all(it == "ojo" for it in self.items)
        tiene_boca = "boca" in self.items
        if solo_ojos and k > 0.5:                                   # estela de burbujas hacia el chico
            for j in range(3):
                r = (8 - 2 * j) * (0.75 + 0.25 * math.sin(t * 3 - j * 0.9))
                bx = px + ux * (largo * 0.98 + 16 + j * 24)
                by = py + uy * (largo * 0.98 + 16 + j * 24)
                pygame.draw.circle(s, INK, (int(bx), int(by)), int(r) + 3)
                pygame.draw.circle(s, papel, (int(bx), int(by)), int(r))
        if tiene_boca and k > 0.6 and fuerza > 0.25:
            ondas_voz(s, px, py, largo, ux, uy, t, self.seed, fuerza * k)

        pts = blob_points(px, py, rx, ry, self.rot, self.seed, t, 1 + 1.5 * fuerza)
        pygame.draw.polygon(s, mix(bg, (0, 0, 30), 0.35), [(x + 8, y + 10) for x, y in pts])
        poli(s, papel, pts, 5)
        self.rayado(s, px, py, rx, ry)
        if k < 0.35:
            return

        vertical = ry >= rx
        n = len(self.items)
        paso = 2 * largo * 0.64 / n
        for i, it in enumerate(self.items):
            off = (i - (n - 1) / 2) * paso
            cx = px if vertical else px + off
            cy = py + off if vertical else py
            if it == "boca":
                ab = (0.08 + 0.92 * fuerza) * abs(math.sin(t * (2.2 + 3 * fuerza) + self.seed + i * 1.7))
                ab *= (1 - sale)
                w, h = corto * 1.3, corto * 0.95
                sc = min(1.0, paso * 0.95 / (h if vertical else w))
                boca_ente(s, cx, cy, w * sc, h * sc, ab, self.seed + i)
            elif it == "ojo":
                R = min(corto * 0.5, paso * 0.46)
                bl = 0.9 * max(0.0, math.sin((t + self.seed * 1.3) * 2.3)) ** 24
                cierre = max(0.28 * (1 - sale), bl, sale * 0.85)
                ojo_ente(s, cx, cy, R, ux, uy, cierre, papel)
            else:
                tubo(s, cx, cy, min(paso * 0.95, largo), vertical, t, self.seed + i,
                     max(6, int(corto * 0.26)), 0.5 * fuerza)


# llega / se_va: segundos en que aparece y en que se deshace al despertar el chico
ENTES = [
    Ente(85, 85, 48, 32, 0.1, ["ojo"], 0.0, 8.6, 1),
    Ente(80, 330, 55, 135, 0.15, ["ojo", "boca", "onda"], 0.0, 6.4, 2),
    Ente(210, 140, 38, 75, -0.2, ["onda", "boca"], 0.0, 7.4, 3),
    Ente(415, 135, 140, 60, 0.08, ["boca", "ojo", "onda"], 0.0, 5.8, 4),
    Ente(575, 55, 80, 38, 0.3, ["ojo", "ojo"], 0.8, 8.0, 5),
    Ente(585, 480, 52, 150, -0.1, ["boca", "onda", "ojo"], 0.0, 7.0, 6),
    Ente(90, 700, 70, 130, -0.25, ["onda", "boca", "ojo"], 1.2, 9.2, 7),
    Ente(45, 560, 30, 38, 0.0, ["ojo"], 2.0, 8.8, 8),
    Ente(560, 810, 85, 70, 0.4, ["boca", "onda"], 1.6, 9.6, 9),
    Ente(500, 300, 45, 62, 0.3, ["ojo", "boca"], 2.4, 7.8, 10),
    Ente(140, 440, 40, 56, -0.3, ["boca"], 2.8, 6.9, 11),
    Ente(300, 80, 50, 40, 0.0, ["ojo"], 3.2, 8.2, 12),
]


# ------------------------------------------------------------------ partículas
class Mota:
    """Burbuja de tinta (al deshacerse una voz) o chispa de luz (amanecer)."""

    def __init__(self, x, y, r, tipo):
        self.x, self.y, self.r, self.tipo = x, y, r, tipo
        self.vx = random.uniform(-14, 14)
        self.vy = random.uniform(-46, -16) if tipo == "burbuja" else random.uniform(-14, -4)
        self.dur = random.uniform(1.8, 3.4) if tipo == "burbuja" else random.uniform(3.0, 6.0)
        self.vida = 1.0
        self.fase = random.uniform(0, TAU)

    def update(self, dt):
        self.vida -= dt / self.dur
        self.x += (self.vx + math.sin(self.fase + self.vida * 6) * 9) * dt
        self.y += self.vy * dt

    def dibujar(self, s):
        k = smooth(0.0, 0.3, self.vida) * (1 if self.tipo == "burbuja" else smooth(1.0, 0.8, self.vida) + 0.0)
        if self.tipo == "luz":
            k = smooth(0.0, 0.3, self.vida) * smooth(0.0, 0.2, 1.0 - self.vida)
        r = self.r * k
        if r < 1:
            return
        x, y = int(self.x), int(self.y)
        if self.tipo == "burbuja":
            pygame.draw.circle(s, INK, (x, y), int(r) + 2)
            pygame.draw.circle(s, PAPEL, (x, y), int(r))
            if r > 4:
                arco(s, (255, 255, 255), x, y, r * 0.6, r * 0.6, 1.9, 2.9, 2)
        else:
            pygame.draw.circle(s, (255, 246, 214), (x, y), int(r))
            if r > 2.4:
                tline(s, (255, 246, 214), (x - r * 2, y), (x + r * 2, y), 1)
                tline(s, (255, 246, 214), (x, y - r * 2), (x, y + r * 2), 1)


# ------------------------------------------------------------------ personaje
RX, RY = 148, 170


class Personaje:
    def __init__(self):
        rnd = random.Random(11)
        self.pinchos = [(i / 79, rnd.uniform(28, 70), rnd.uniform(-0.35, 0.35),
                         rnd.uniform(0, TAU), rnd.uniform(8, 15)) for i in range(80)]
        self.flequillo = [rnd.uniform(14, 36) for _ in range(11)]
        self.mirada = [0.0, 0.0]
        self.destino = [0.0, 0.0]
        self.t_mirada = 0.0
        self.sig_parp = 1.5
        self.parp_t = -1.0

    # ---- cuerpo, bata y suéter
    def cuerpo(self, s, cx, top):
        pygame.draw.polygon(s, (168, 168, 174),
                            [(cx - 100, top - 15), (cx + 100, top - 15), (cx + 140, H), (cx - 140, H)])
        y = top + 14
        while y < H:
            w = 100 + (y - top) * 0.2
            pygame.draw.line(s, (112, 112, 122), (cx - w, y), (cx + w, y), 4)
            y += 15
        # sombra a la izquierda (como en el dibujo)
        pygame.draw.polygon(s, INK, [(cx - 100, top - 15), (cx - 30, top - 15), (cx - 55, H), (cx - 140, H)])
        for yy in range(int(top) + 6, H, 11):
            pygame.draw.line(s, (80, 80, 92), (cx - 28, yy), (cx - 6, yy - 10), 4)
        for side in (-1, 1):
            pts = [(cx + side * 100, top - 15), (cx + side * 235, top + 45),
                   (cx + side * 320, H), (cx + side * 140, H)]
            poli(s, (240, 238, 234), pts, 6)
            tline(s, INK, (cx + side * 100, top - 15), (cx + side * 84, top + 80), 5)
            tline(s, INK, (cx + side * 170, top + 20), (cx + side * 200, top + 160), 4)

    def cuello(self, s, cx, hy, top, jaw):
        pts = [(cx - 52, hy + 100), (cx + 52, hy + 100), (cx + 58, top), (cx - 58, top)]
        poli(s, PIEL, pts, 6)
        # hachurado bajo la barbilla
        pygame.draw.polygon(s, INK, [(cx - 56, hy + 120), (cx + 56, hy + 120),
                                     (cx + 40, hy + 175 + jaw), (cx - 40, hy + 175 + jaw)])
        for i in range(-5, 6):
            x = cx + i * 9
            tline(s, PIEL, (x, hy + 178 + jaw), (x + 12, hy + 215 + jaw), 4)
        for i in range(-5, 0):
            x = cx + i * 9
            tline(s, INK, (x, top - 60), (x + 14, top - 15), 4)
        # cuello del suéter
        r = pygame.Rect(cx - 84, int(top) - 34, 168, 46)
        pygame.draw.ellipse(s, (160, 160, 166), r)
        pygame.draw.ellipse(s, INK, r, 6)
        for i in range(-7, 8):
            x = cx + i * 11
            tline(s, (100, 100, 110), (x, top - 28), (x, top + 4), 2)

    # ---- pelo
    def pelo_atras(self, s, cx, hy, t, dh):
        hc = (cx, hy - 62)
        tb = int(t * 10)
        pygame.draw.ellipse(s, INK, (hc[0] - 172, hc[1] - 185, 344, 340))
        for side in (-1, 1):
            pygame.draw.polygon(s, INK, [(cx + side * (RX - 4), hy - 60), (cx + side * (RX + 24), hy - 40),
                                         (cx + side * (RX + 26), hy + 70), (cx + side * (RX - 8), hy + 100)])
        for idx, (fr, L0, ao, ph, wd) in enumerate(self.pinchos):
            a = math.pi * 0.88 + fr * math.pi * 1.24
            bx = hc[0] + 168 * math.cos(a) - math.cos(a) * 12
            by = hc[1] + 175 * math.sin(a) - math.sin(a) * 12
            ang = a + ao * (1 + dh) + math.sin(t * 1.3 + ph) * 0.05
            L = L0 * (1 + 0.07 * math.sin(t * 2.0 + ph))
            tip = (bx + math.cos(ang) * L + ruido(idx, tb) * 1.4,
                   by + math.sin(ang) * L + ruido(idx + 99, tb) * 1.4)
            nx, ny = -math.sin(ang), math.cos(ang)
            pygame.draw.polygon(s, INK, [(bx + nx * wd, by + ny * wd), tip, (bx - nx * wd, by - ny * wd)])

    def flequillo_dibujar(self, s, cx, hy, t):
        y0 = hy - 132
        left = cx - RX - 8
        wdt = 2 * RX + 16
        n = len(self.flequillo)
        step = wdt / n
        pts = [(left, hy - 185), (left + wdt, hy - 185), (left + wdt, y0)]
        for i in range(n - 1, -1, -1):
            xt = left + (i + 0.5) * step + math.sin(t * 1.2 + i) * 1.2
            L = self.flequillo[i] + math.sin(t * 1.7 + i) * 1.5
            pts.append((xt, y0 + L + ruido(i, int(t * 10)) * 1.2))
            pts.append((left + i * step, y0))
        pygame.draw.polygon(s, INK, pts)

    # ---- ojo grande del dibujo (abierto, entornado o cerrado)
    def ojo(self, s, ex, ey, R, op, lx, ly, pr):
        ex, ey = int(ex), int(ey)
        pygame.draw.circle(s, PIEL, (ex, ey), R)

        def cerrada(u):
            return R * 0.22 * (1 - u * u)

        us = [i / 18 * 2 - 1 for i in range(19)]
        sup = [(u * R, lerp(cerrada(u), -R * math.sqrt(max(0.0, 1 - u * u)), op)) for u in us]
        inf = [(u * R, lerp(cerrada(u), R * math.sqrt(max(0.0, 1 - u * u)), op)) for u in us]
        if op > 0.03:
            size = 2 * R + 12
            off = size // 2
            g = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.circle(g, (255, 255, 255, 255), (off, off), R)
            pygame.draw.circle(g, INK + (255,), (off + int(lx), off + int(ly)), int(pr))
            pygame.draw.circle(g, (255, 255, 255, 255),
                               (off + int(lx - pr * 0.35), off + int(ly - pr * 0.35)), max(2, int(pr * 0.22)))
            m = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.polygon(m, (255, 255, 255, 255), [(off + x, off + y) for x, y in sup + inf[::-1]])
            g.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            s.blit(g, (ex - off, ey - off))
            tpoly(s, INK, [(ex + x, ey + y) for x, y in inf], 5)
        tpoly(s, INK, [(ex + x, ey + y) for x, y in sup], 7 + (1 - op) * 3)
        if op < 0.6:                                              # pestañas del ojo dormido
            m_ = 1 - op / 0.6
            for i in range(5):
                u = -0.7 + i * 0.35
                x0 = ex + u * R
                y0 = ey + lerp(cerrada(u), -R * math.sqrt(1 - u * u), op)
                tline(s, INK, (x0, y0), (x0 + u * 6, y0 + 5 + 9 * m_), 4)
        pygame.draw.circle(s, INK, (ex, ey), R, int(4 + 3 * op))

    # ---- dibujo completo
    def dibujar(self, s, t, e, dt, mundo):
        sd = e.sueno
        br = math.sin(t * (1.0 + 0.5 * (1 - sd)))                  # respiración lenta
        by = br * (2.0 + 2.5 * sd)
        cx = W // 2
        hcx = cx + int(11 * sd + 2 * math.sin(t * 0.6))             # cabeza ladeada al dormir
        jolt = 12 * bump(t, 4.9, 6.3)                               # sobresalto al despertar
        hy = 470 + 20 * sd + by * 0.6 - jolt - 6 * e.bostezo - mundo.pulso * sd * 2
        top = 700 + by + 8 * sd

        # boca: entreabierta al dormir, bostezo al despertar
        o = max(sd * (0.13 + 0.05 * br), e.bostezo * 0.95)
        jaw = 0.25 * o
        dh = 0.12 * sd

        self.cuerpo(s, cx, top)
        self.pelo_atras(s, hcx, hy, t, dh)
        self.cuello(s, hcx, hy, top, int(jaw * RY))

        # cabeza
        tb = int(t * 10)
        pts = []
        for i in range(64):
            a = i / 64 * TAU
            x = math.cos(a) * RX
            y = math.sin(a) * RY
            if y > 0:
                x *= 1 - 0.22 * (y / RY) ** 2
                y *= 1 + jaw
            pts.append((hcx + x + ruido(i, tb) * 0.9, hy + y + ruido(i + 70, tb) * 0.9))
        for side in (-1, 1):                                        # orejas
            r = pygame.Rect(0, 0, 40, 64)
            r.center = (hcx + side * (RX + 2), hy + 22)
            pygame.draw.ellipse(s, PIEL, r)
            pygame.draw.ellipse(s, INK, r, 6)
            arco(s, INK, r.x + 17, r.y + 29, 9, 15, 0.5, 4.5, 4)
        poli(s, PIEL, pts, 8)

        # arrugas de las mejillas (líneas del dibujo)
        for side in (-1, 1):
            for k in range(2 + int(sd * 2)):
                x0 = hcx + side * (66 + k * 15)
                y0 = hy + 18 + k * 4
                ln = 70 + k * 8
                trazo = []
                for q in range(8):
                    u = q / 7
                    trazo.append((x0 + side * (6 * math.sin(u * 3 + k) + u * 6), y0 + u * ln))
                tpoly(s, INK, trazo, 4)

        # nariz
        tpoly(s, INK, [(hcx + 3, hy + 28), (hcx + 10, hy + 52), (hcx + 1, hy + 57)], 6)

        # ---- ojos
        R = 50
        ey = hy - 18
        self.t_mirada -= dt
        if self.t_mirada <= 0:
            self.t_mirada = random.uniform(0.9, 2.6)
            rg = 3 + 16 * (1 - e.enfoque)
            if e.enfoque > 0.95 and random.random() < 0.5:
                rg = 2
            self.destino = [random.uniform(-rg, rg), random.uniform(-rg * 0.6, rg * 0.6)]
        k = min(1.0, dt * 3.0)
        self.mirada[0] += (self.destino[0] - self.mirada[0]) * k
        self.mirada[1] += (self.destino[1] - self.mirada[1]) * k
        pr = lerp(41, 30, e.enfoque) + mundo.pulso * 0.6

        op = e.ojos * (1 - 0.55 * e.bostezo)
        if self.parp_t < 0:                                          # parpadeos ya despierto
            if e.ojos > 0.98 and t > 10.0:
                self.sig_parp -= dt
                if self.sig_parp <= 0:
                    self.parp_t = 0.0
        else:
            self.parp_t += dt / 0.22
            if self.parp_t >= 1:
                self.parp_t = -1.0
                self.sig_parp = random.uniform(2.0, 5.0)
        if self.parp_t >= 0:
            op *= 1 - math.sin(math.pi * self.parp_t)

        for side in (-1, 1):
            ex = hcx + side * 68
            mx = max(0.0, R - pr - 5)
            lx = max(-mx, min(mx, self.mirada[0]))
            ly = max(-mx, min(mx, self.mirada[1]))
            self.ojo(s, ex, ey, R, clamp01(op), lx, ly, pr)
            # ojeras (más marcadas mientras duerme)
            for q in range(1 + int(sd * 2)):
                arco(s, INK, ex, ey + R * (0.55 + q * 0.18) + R * 0.45, R * 0.9, R * 0.45,
                     math.pi * 1.15, math.pi * 1.85, 4)
            # cejas: preocupadas al dormir, se levantan al despertar y se relajan
            by0 = ey - R - 28 - 10 * bump(t, 5.2, 8.5)
            inner = (ex - side * R * 0.5, by0 - 14 * sd)
            outer = (ex + side * R * 1.0, by0 + 8 * sd)
            mid = ((inner[0] + outer[0]) / 2, min(inner[1], outer[1]) - 8)
            tpoly(s, INK, [inner, mid, outer], 9)
            if sd > 0.3:                                              # ceño de pesadilla
                tline(s, INK, (hcx + side * 7, by0 - 4), (hcx + side * 9, by0 + 8 + 10 * sd), 4)

        # rubor al sonreír
        if e.sonrisa > 0.05:
            for side in (-1, 1):
                for i in range(3):
                    x = hcx + side * (84 + i * 11)
                    tline(s, ROSA, (x, hy + 38), (x - side * 5, hy + 38 + 16 * e.sonrisa), 3)

        # ---- flequillo (encima de la frente)
        self.flequillo_dibujar(s, hcx, hy, t)

        # ---- boca
        my = hy + 85
        w = 42 + 50 * e.bostezo + 14 * e.sonrisa
        if o < 0.06:
            a = lerp(-4, 10, e.sonrisa)
            trazo = []
            for q in range(9):
                u = q / 8 * 2 - 1
                trazo.append((hcx + u * w / 2, my + 8 + a * (1 - u * u) - 5 * e.sonrisa * u * u))
            tpoly(s, INK, trazo, 8)
        else:
            h = 110 * o
            sup, inf = [], []
            for q in range(15):
                u = q / 14 * 2 - 1
                sup.append((hcx + u * w / 2, my - 6 * (1 - u * u)))
                inf.append((hcx + u * w / 2, my + h * (1 - u * u) ** 0.7))
            poly = sup + inf[::-1]
            pygame.draw.polygon(s, INK, poly)
            if h > 18:
                for q in range(-2, 3):
                    pygame.draw.rect(s, PAPEL, (int(hcx + q * w * 0.15 - 7), int(my - 6 * (1 - (q * 0.3) ** 2)),
                                                14, int(min(20, h * 0.28))))
            if h > 55:
                lg = pygame.Rect(0, 0, int(w * 0.45), int(h * 0.26))
                lg.center = (int(hcx), int(my + h * 0.7))
                pygame.draw.ellipse(s, (196, 70, 84), lg)
            tpoly(s, INK, poly + [poly[0]], 8)


# ------------------------------------------------------------------ sonido
def crear_sonidos():
    rate = 22050
    # latido suave: "lub-dub"
    lat = array("h")
    for i in range(int(rate * 0.45)):
        tt = i / rate
        v = math.sin(TAU * 52 * tt) * math.exp(-tt * 18)
        t2 = tt - 0.17
        if t2 > 0:
            v += 0.7 * math.sin(TAU * 46 * t2) * math.exp(-t2 * 20)
        lat.append(int(max(-1, min(1, v)) * 20000))
    # murmullo de voces (ruido filtrado y modulado)
    n = rate * 2
    mur = array("h")
    v = 0.0
    for i in range(n):
        v = v * 0.93 + random.uniform(-1, 1) * 0.07
        mod = 0.6 + 0.4 * math.sin(TAU * 4 * i / n)
        mur.append(int(max(-1, min(1, v * 5 * mod)) * 9000))
    # campanita del amanecer: arpegio do-mi-sol
    cam = array("h")
    dur = 2.6
    for i in range(int(rate * dur)):
        tt = i / rate
        v = 0.0
        for k, f in enumerate((523.25, 659.25, 783.99, 1046.5)):
            t0 = tt - k * 0.2
            if t0 > 0:
                v += (math.sin(TAU * f * t0) + 0.3 * math.sin(TAU * f * 2.01 * t0)) * math.exp(-t0 * 2.6)
        cam.append(int(max(-1, min(1, v * 0.32)) * 14000))
    return (pygame.mixer.Sound(buffer=lat.tobytes()),
            pygame.mixer.Sound(buffer=mur.tobytes()),
            pygame.mixer.Sound(buffer=cam.tobytes()))


# ------------------------------------------------------------------ mundo
class Mundo:
    def __init__(self):
        self.reiniciar()

    def reiniciar(self):
        self.t = 0.0
        self.motas = []
        self.latido_t = 0.4
        self.pulso = 0.0
        self.campana = False
        self.acum_luz = 0.0
        for en in ENTES:
            en.acum = 0.0

    def emitir(self, px, py, rx, ry, rot):
        if len(self.motas) > 170:
            return
        a = random.uniform(0, TAU)
        r = math.sqrt(random.random())
        x, y = math.cos(a) * rx * r, math.sin(a) * ry * r
        c, sn = math.cos(rot), math.sin(rot)
        self.motas.append(Mota(px + x * c - y * sn, py + x * sn + y * c, random.uniform(3, 8), "burbuja"))

    def avanzar(self, dt):
        """Avanza el tiempo; devuelve (estado, hubo_latido)."""
        self.t += dt
        e = estado(self.t)
        latido = False
        self.latido_t -= dt
        if self.latido_t <= 0:
            self.latido_t = 60.0 / (56 + 12 * (1 - e.sueno))
            self.pulso = 1.0
            latido = True
        self.pulso = max(0.0, self.pulso - dt * 3.5)
        # chispas de luz una vez que amanece
        if e.alba > 0.35:
            self.acum_luz += dt * 4 * e.alba
            while self.acum_luz >= 1:
                self.acum_luz -= 1
                if len(self.motas) < 170:
                    self.motas.append(Mota(random.uniform(30, W - 30), random.uniform(250, H - 100),
                                           random.uniform(1.6, 3.2), "luz"))
        for m in self.motas:
            m.update(dt)
        self.motas = [m for m in self.motas if m.vida > 0]
        return e, latido

    def dibujar_motas(self, s, tipo):
        for m in self.motas:
            if m.tipo == tipo:
                m.dibujar(s)


# ------------------------------------------------------------------ render
def componer(canvas, e, dt, mundo, pers):
    t = mundo.t
    canvas.fill(PAPEL)
    bg = mix(NOCHE, AZUL, e.alba ** 0.85)
    bg = mix(bg, (120, 206, 240), 0.35 * smooth(10.0, 16.0, t))
    bg = mix(bg, (255, 255, 255), mundo.pulso * 0.04 * e.sueno)
    pygame.draw.rect(canvas, bg, (14, 34, W - 28, H - 48), border_radius=10)
    canvas.blit(TRAZOS, (0, 0))
    if e.alba > 0.01:
        SOL.set_alpha(int(210 * e.alba))
        canvas.blit(SOL, (W - 560, -300))
    for en in ENTES:
        en.dibujar(canvas, t, e, dt, mundo, bg)
    mundo.dibujar_motas(canvas, "burbuja")
    if e.alba > 0.01:
        HACES.set_alpha(int(255 * smooth(0.05, 0.8, e.alba)))
        canvas.blit(HACES, (0, 0))
    pers.dibujar(canvas, t, e, dt, mundo)
    mundo.dibujar_motas(canvas, "luz")
    dibujar_espiral(canvas)


def postproceso(canvas, e, mundo, destino, con_grano=True):
    t = mundo.t
    zoom = 1.0 + 0.04 * (1 - smooth(4.5, 12.0, t)) + 0.006 * math.sin(t * 0.5) + 0.01 * mundo.pulso * e.sueno
    zw, zh = int(W * zoom), int(H * zoom)
    jit = 1.2 * (0.3 + 0.7 * e.sueno)                      # leve temblor de proyector
    ox = (W - zw) // 2 + int(random.uniform(-jit, jit))
    oy = (H - zh) // 2 + int(random.uniform(-jit, jit))
    destino.fill((10, 10, 12))
    if zoom > 1.002:
        destino.blit(pygame.transform.smoothscale(canvas, (zw, zh)), (ox, oy))
    else:
        destino.blit(canvas, (ox, oy))

    velo(destino, (6, 10, 40), 58 * e.sueno)                 # penumbra del sueño
    velo(destino, (255, 206, 140), 30 * e.alba)               # luz cálida de la mañana
    velo(destino, (255, 255, 255), 70 * bump(t, 5.6, 7.8))    # destello al abrir los ojos
    VINETA.set_alpha(int(50 + 120 * e.sueno))
    destino.blit(VINETA, (0, 0))

    if con_grano:
        grano().aplicar(destino, lerp(46, 34, e.alba), lerp(26, 16, e.alba))
        polvo(destino)


class AnimacionCatarsis:
    """Renderiza la escena del despertar (por ejemplo como pantalla de transición)."""

    def __init__(self, ancho, alto):
        self.ancho = ancho
        self.alto = alto
        self.canvas = pygame.Surface((W, H))
        self.frame = pygame.Surface((W, H))
        self.mundo = Mundo()
        self.personaje = Personaje()
        self.inicio = 0.0
        self.ultimo_tiempo = None

    def iniciar(self):
        self.mundo.reiniciar()
        self.inicio = 0.0
        self.ultimo_tiempo = None
        self.personaje = Personaje()

    def dibujar(self, destino, tiempo):
        if self.ultimo_tiempo is None:
            dt = 1.0 / FPS
            self.inicio = tiempo
        else:
            dt = min(0.05, max(0.0, tiempo - self.ultimo_tiempo))
        self.ultimo_tiempo = tiempo
        transcurrido = max(0.0, tiempo - self.inicio)

        e, _ = self.mundo.avanzar(dt)
        componer(self.canvas, e, dt, self.mundo, self.personaje)
        postproceso(self.canvas, e, self.mundo, self.frame)

        imagen = pygame.transform.smoothscale(self.frame, (self.ancho, self.alto))
        destino.blit(imagen, (0, 0))

        # entrada: fundido desde negro
        if transcurrido < 0.8:
            v = pygame.Surface((self.ancho, self.alto))
            v.set_alpha(int(255 * (1 - transcurrido / 0.8)))
            destino.blit(v, (0, 0))


def play_catarsis_animation(
    screen,
    clock=None,
    exit_text="EXIT",
    exit_delay=5.0,
    button_renderer=None,
):
    """Muestra Catarsis en la ventana actual hasta que se pulse salir."""
    clock = clock or pygame.time.Clock()
    animacion = AnimacionCatarsis(*screen.get_size())
    animacion.iniciar()
    inicio = pygame.time.get_ticks()

    while True:
        tiempo = (pygame.time.get_ticks() - inicio) / 1000.0
        ancho, alto = screen.get_size()
        if button_renderer is not None:
            sx = ancho / button_renderer.ancho
            sy = alto / button_renderer.alto
            original = button_renderer.boton_salir
            boton = pygame.Rect(
                round(original.x * sx),
                round(original.y * sy),
                round(original.width * sx),
                round(original.height * sy),
            )
            escala_ui = min(sx, sy) * button_renderer._escala()
            fuente = pygame.font.SysFont(
                "comicsansms", max(14, round(22 * escala_ui)), bold=True
            )
        else:
            escala = min(ancho / W, alto / H)
            fuente = pygame.font.SysFont(None, max(18, round(26 * escala)), bold=True)
            boton = pygame.Rect(0, 0, 170, 54)
            boton.bottomright = (ancho - 26, alto - 26)

        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                pygame.event.post(evento)
                return False
            if (
                tiempo >= exit_delay
                and evento.type == pygame.MOUSEBUTTONDOWN
                and evento.button == pygame.BUTTON_LEFT
                and boton.collidepoint(evento.pos)
            ):
                return False

        animacion.dibujar(screen, tiempo)
        hover = boton.collidepoint(pygame.mouse.get_pos())
        if button_renderer is not None:
            button_renderer.reloj_pulso = tiempo
            rect_dibujo = button_renderer._dibujar_boton_comic(
                screen, boton, hover
            )
            button_renderer._texto_centrado(
                screen, exit_text, fuente, rect_dibujo.center, (255, 255, 255)
            )
        else:
            pygame.draw.rect(
                screen,
                (105, 44, 58) if hover else (62, 38, 48),
                boton,
                border_radius=8,
            )
            pygame.draw.rect(screen, (245, 220, 190), boton, 2, border_radius=8)
            superficie_texto = fuente.render(exit_text, True, (255, 255, 255))
            screen.blit(
                superficie_texto,
                superficie_texto.get_rect(center=boton.center),
            )

        pygame.display.flip()
        clock.tick(60)


# ------------------------------------------------------------------ principal
def main():
    try:
        pygame.mixer.pre_init(22050, -16, 1, 512)
    except Exception:
        pass
    pygame.init()
    try:
        screen = pygame.display.set_mode((W, H), pygame.SCALED | pygame.RESIZABLE)
    except Exception:
        screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Las voces - el despertar")
    clock = pygame.time.Clock()
    mundo = Mundo()
    pers = Personaje()
    canvas = pygame.Surface((W, H))
    con_grano = True

    latido = murmullo = campana = None
    sonido = True
    try:
        latido, murmullo, campana = crear_sonidos()
        murmullo.set_volume(0.0)
        murmullo.play(loops=-1)
    except Exception:
        sonido = False

    while True:
        dt = min(0.05, clock.tick(FPS) / 1000.0)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if ev.key == pygame.K_r:
                    mundo.reiniciar()
                    pers = Personaje()
                if ev.key == pygame.K_g:
                    con_grano = not con_grano
                if ev.key == pygame.K_SPACE and mundo.t < T_DESPIERTA - 0.5:
                    mundo.t = T_DESPIERTA - 0.5
                if ev.key == pygame.K_m and latido:
                    sonido = not sonido
                    if not sonido:
                        murmullo.set_volume(0.0)

        e, hubo_latido = mundo.avanzar(dt)

        if latido and sonido:
            if hubo_latido:
                latido.set_volume(0.30 - 0.14 * (1 - e.sueno))
                latido.play()
            murmullo.set_volume(0.03 + 0.5 * e.voces)
            if not mundo.campana and mundo.t >= T_DESPIERTA + 0.4:
                mundo.campana = True
                campana.set_volume(0.6)
                campana.play()

        componer(canvas, e, dt, mundo, pers)
        postproceso(canvas, e, mundo, screen, con_grano)

        # final: se desvanece a negro y vuelve a empezar
        fin = mundo.t - (T_REINICIO - 3.0)
        if fin > 0:
            negro = pygame.Surface((W, H))
            negro.set_alpha(int(255 * clamp01(fin / 2.5)))
            screen.blit(negro, (0, 0))
            if mundo.t > T_REINICIO:
                mundo.reiniciar()
                pers = Personaje()

        pygame.display.flip()


if __name__ == "__main__":
    main()