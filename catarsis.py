"""
LAS VOCES  -  catarsis
----------------------
Todo está dibujado por código (no usa ninguna imagen).

La escena tiene dos tiempos:
  1. DESESPERACIÓN (0 - 7 s): todo bajo una capa de opacidad gris. Las voces rodean
     al chico, que tiembla, suda, tiene los ojos desorbitados y grita; hasta la
     cámara tiembla.
  2. CALMA (de 7 s en adelante): las voces se deshacen en burbujas, el gris se
     disipa y el fondo se vuelve azul (20, 114, 222). Suspira y se queda cansado:
     párpados pesados, ojeras, hombros caídos, el pelo se baja y cabecea de sueño.

El personaje está hecho en PIXEL ART: se dibuja en un lienzo pequeño con formas
rectas y esquinas cortadas a 45° (sin curvas) y se amplía sin suavizar. Pierde
detalle a propósito. Cambia PX para hacer los píxeles más grandes o más pequeños.

Además lleva grano de película animado, polvo y rayones, una capa de pixelado y
un tramado (dither) de sombras y luces.

Requisitos:  pip install pygame

Controles:
  ESPACIO  -> saltar a la calma
  G        -> activar / quitar el grano
  P        -> activar / quitar el pixelado
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
T_CALMA = 7.0              # segundo en que la desesperación se suelta y llega la calma
T_REINICIO = 30.0          # segundo en que la escena se reinicia (en main)
PIXEL = 2                  # tamaño del pixelado (1 = sin pixelar, 2-4 = más retro)
CELDA = 2                  # tamaño de cada punto del tramado de sombras
TAU = math.tau

INK = (14, 14, 20)
PAPEL = (246, 242, 236)
PIEL = (253, 251, 248)
AZUL_CALMA = (20, 114, 222)   # color de la calma
GRIS_CRISIS = (66, 68, 76)    # fondo durante la desesperación
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


def bez(p0, p1, p2, n=6):
    """Curva de Bézier cuadrática de p0 a p2 con control p1."""
    out = []
    for i in range(n + 1):
        u = i / n
        a, b, c = (1 - u) ** 2, 2 * u * (1 - u), u * u
        out.append((a * p0[0] + b * p1[0] + c * p2[0], a * p0[1] + b * p1[1] + c * p2[1]))
    return out


def spline(pts, n=3):
    """Catmull-Rom cerrada: convierte un polígono en un contorno curvo y continuo."""
    m = len(pts)
    out = []
    for i in range(m):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % m], pts[(i + 2) % m]
        for k in range(n):
            u = k / n
            u2, u3 = u * u, u * u * u
            out.append((0.5 * (2 * p1[0] + (-p0[0] + p2[0]) * u + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * u2
                               + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * u3),
                        0.5 * (2 * p1[1] + (-p0[1] + p2[1]) * u + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * u2
                               + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * u3)))
    return out


def redondear(pts, r=22, n=6):
    """Redondea las esquinas de un polígono con radio fijo (sin encoger los lados largos)."""
    m = len(pts)
    out = []
    for i in range(m):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % m]
        d1 = math.hypot(p0[0] - p1[0], p0[1] - p1[1]) or 1.0
        d2 = math.hypot(p2[0] - p1[0], p2[1] - p1[1]) or 1.0
        r1, r2 = min(r, d1 / 2), min(r, d2 / 2)
        a = (p1[0] + (p0[0] - p1[0]) / d1 * r1, p1[1] + (p0[1] - p1[1]) / d1 * r1)
        b = (p1[0] + (p2[0] - p1[0]) / d2 * r2, p1[1] + (p2[1] - p1[1]) / d2 * r2)
        out += bez(a, p1, b, n)
    return out


def poli(s, relleno, pts, w, modo=None, r=22):
    """Polígono relleno con contorno de tinta grueso.
    modo 'spline' = contorno orgánico; 'redondo' = esquinas redondeadas; None = recto."""
    if modo == "spline":
        pts = spline(pts)
    elif modo == "redondo":
        pts = redondear(pts, r)
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
    """Todo lo que cambia entre la desesperación y la calma, derivado del tiempo."""
    __slots__ = ("panico", "calma", "gris", "cansancio", "suspiro", "voces")


def estado(t):
    e = Estado()
    e.panico = 1.0 - smooth(6.6, 9.6, t)                  # 1 desesperado  ->  0
    e.calma = smooth(7.0, 12.0, t)                        # fondo: gris -> azul
    e.gris = 1.0 - smooth(7.0, 13.0, t)                   # capa de opacidad gris que se disipa
    e.cansancio = smooth(8.6, 13.5, t)                    # párpados pesados, ojeras, hombros caídos
    e.suspiro = bump(t, 7.4, 10.4)                        # exhalación larga al soltar la tensión
    e.voces = smooth(0.0, 1.5, t) * (1.0 - smooth(6.4, 11.0, t))
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
            v.set_at((x, y), (150, 200, 255, int(255 * a)))
    return pygame.transform.smoothscale(v, (820, 820))


def crear_haces():
    """Haces de luz de la mañana que entran en diagonal."""
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    for x0, ancho, a in ((330, 70, 50), (470, 120, 36), (600, 60, 56), (200, 40, 30), (80, 30, 22)):
        pts = [(x0, -20), (x0 + ancho, -20), (x0 + ancho - 560, H + 20), (x0 - 560, H + 20)]
        pygame.draw.polygon(s, (190, 222, 255, a * 2 // 3), pts)
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


# ------------------------------------------------------------------ tramado de píxeles
# Matriz de Bayer 4x4: decide qué puntos se encienden para simular medios tonos.
BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))
SOMBRA_MULT = (150, 160, 212)      # multiplica: oscurece/enfría las zonas claras (la tinta no cambia)
LUZ_ADD = (36, 30, 12)             # suma: brillo cálido en las zonas iluminadas


def crear_tramado(fase):
    """Capas de sombra (multiplicar) y luz (sumar) con puntos ordenados.
    La luz viene de arriba a la derecha; abajo a la izquierda queda en sombra."""
    w, h = W // CELDA, H // CELDA
    sombra = pygame.Surface((w, h))
    luz = pygame.Surface((w, h))
    sombra.fill((255, 255, 255))
    luz.fill((0, 0, 0))
    for y in range(h):
        v = y / h
        fila = BAYER[(y + fase) & 3]
        for x in range(w):
            u = x / w
            claridad = 0.55 * u + 0.45 * (1 - v)
            umbral = (fila[(x + fase) & 3] + 0.5) / 16
            if (0.55 - claridad) / 0.55 > umbral:
                sombra.set_at((x, y), SOMBRA_MULT)
            elif (claridad - 0.64) / 0.36 > umbral:
                luz.set_at((x, y), LUZ_ADD)
    return (pygame.transform.scale(sombra, (W, H)), pygame.transform.scale(luz, (W, H)))


def tramado(fase):
    if "tramado" not in _CACHE:
        _CACHE["tramado"] = [crear_tramado(0), crear_tramado(1)]
    return _CACHE["tramado"][fase & 1]


def precalentar():
    """Crea las texturas pesadas una sola vez (llamar tras abrir la ventana)."""
    grano()
    tramado(0)


def pixelar(destino, tam):
    if tam > 1:
        chico = pygame.transform.scale(destino, (W // tam, H // tam))
        destino.blit(pygame.transform.scale(chico, (W, H)), (0, 0))


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
        fuerza = e.panico
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
        pygame.draw.polygon(s, mix(bg, (0, 0, 30), 0.35), [(x + 8, y + 10) for x, y in spline(pts)])
        poli(s, papel, pts, 5, "spline")
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
    Ente(85, 85, 48, 32, 0.1, ["ojo"], 0.0, 10.6, 1),
    Ente(80, 330, 55, 135, 0.15, ["ojo", "boca", "onda"], 0.0, 8.4, 2),
    Ente(210, 140, 38, 75, -0.2, ["onda", "boca"], 0.0, 9.4, 3),
    Ente(415, 135, 140, 60, 0.08, ["boca", "ojo", "onda"], 0.0, 7.8, 4),
    Ente(575, 55, 80, 38, 0.3, ["ojo", "ojo"], 0.8, 10.0, 5),
    Ente(585, 480, 52, 150, -0.1, ["boca", "onda", "ojo"], 0.0, 9.0, 6),
    Ente(90, 700, 70, 130, -0.25, ["onda", "boca", "ojo"], 1.2, 11.2, 7),
    Ente(45, 560, 30, 38, 0.0, ["ojo"], 2.0, 10.8, 8),
    Ente(560, 810, 85, 70, 0.4, ["boca", "onda"], 1.6, 11.6, 9),
    Ente(500, 300, 45, 62, 0.3, ["ojo", "boca"], 2.4, 9.8, 10),
    Ente(140, 440, 40, 56, -0.3, ["boca"], 2.8, 8.9, 11),
    Ente(300, 80, 50, 40, 0.0, ["ojo"], 3.2, 10.2, 12),
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
            pygame.draw.circle(s, (205, 228, 255), (x, y), int(r))
            if r > 2.4:
                tline(s, (205, 228, 255), (x - r * 2, y), (x + r * 2, y), 1)
                tline(s, (205, 228, 255), (x, y - r * 2), (x, y + r * 2), 1)


# ------------------------------------------------------------------ personaje (pixel art)
# El personaje se dibuja en un lienzo pequeño (LW x LH) usando solo rectángulos, rectas y
# esquinas cortadas a 45° (nada de curvas ni antialias) y después se amplía SIN suavizar:
# cada "píxel" del personaje mide PX x PX píxeles de pantalla. Pierde detalle a propósito.
PX = 4
LW, LH = W // PX, H // PX                  # 160 x 225
CLAVE = (255, 0, 255)                      # color transparente del sprite

P_PIEL = (250, 246, 242)
P_PIEL_S = (212, 206, 216)                 # sombra de la piel
P_OJERA = (118, 126, 178)                  # ojeras azuladas
P_SUDOR = (190, 224, 255)
P_SUETER = (168, 168, 174)
P_SUETER_S = (112, 112, 122)
P_SUETER_O = (84, 84, 96)
P_BATA = (240, 238, 234)
BLANCO = (255, 255, 255)


def rr(s, col, x, y, w, h):
    """Rectángulo en la rejilla del sprite."""
    if w > 0 and h > 0:
        s.fill(col, (int(x), int(y), int(w), int(h)))


def tri(s, col, a, b, c):
    pygame.draw.polygon(s, col, [(int(a[0]), int(a[1])), (int(b[0]), int(b[1])), (int(c[0]), int(c[1]))])


def octogono(hw, alto, corte):
    """Semi-ancho de cada fila de un rectángulo con las esquinas cortadas a 45°."""
    return [hw - max(0, corte - min(i, alto - 1 - i)) for i in range(alto)]


def filas_cabeza(a, sup, inf):
    """Cabeza cuadrada: esquinas superiores cortadas y mandíbula que se estrecha por escalones."""
    out = []
    n = sup + inf
    for i in range(n):
        if i < sup:
            w = a - max(0, 10 - i)
        else:
            w = a - ((i - sup) * 11) // inf - max(0, 3 - (n - 1 - i))
        out.append(w)
    return out


def silueta(s, filas, cx, y0, relleno, borde=INK):
    """Forma definida por semi-anchos por fila, con contorno de 1 píxel."""
    n = len(filas)
    for i, w in enumerate(filas):
        rr(s, borde, cx - w, y0 + i, 2 * w + 1, 1)
    for i in range(1, n - 1):
        w = min(filas[i] - 1, filas[i - 1], filas[i + 1])
        if w >= 0:
            rr(s, relleno, cx - w, y0 + i, 2 * w + 1, 1)


def gota(s, x, y):
    """Gota de sudor."""
    for i, w in enumerate((0, 1, 1, 2, 2, 2, 1)):
        rr(s, P_SUDOR, x - w, y + i, 2 * w + 1, 1)
    rr(s, BLANCO, x - 1, y + 3, 1, 2)


class Personaje:
    def __init__(self):
        rnd = random.Random(11)
        self.pinchos = [(i / 21, rnd.uniform(11, 21), rnd.uniform(-0.3, 0.3),
                         rnd.uniform(0, TAU), rnd.uniform(3.0, 4.6)) for i in range(22)]
        self.flequillo = [rnd.randint(3, 8) for _ in range(9)]
        self.mirada = [0.0, 0.0]
        self.destino = [0.0, 0.0]
        self.t_mirada = 0.0
        self.spr = None

    @staticmethod
    def cabeceo(t, cans):
        """0 -> 1: la cabeza se va cayendo de sueño y se levanta de golpe."""
        if cans < 0.5:
            return 0.0
        ph = (t - 12.0) % 7.0
        return cans * smooth(0.4, 3.2, ph) * (1.0 - smooth(3.2, 3.45, ph))

    # ---- cuerpo, bata y suéter
    def cuerpo(self, s, cx, top):
        for lado in (-1, 1):                                        # solapas de la bata
            pts = [(cx + lado * 24, top - 5), (cx + lado * 60, top + 10),
                   (cx + lado * 82, LH + 2), (cx + lado * 30, LH + 2)]
            pygame.draw.polygon(s, P_BATA, pts)
            pygame.draw.polygon(s, INK, pts, 1)
            pygame.draw.line(s, INK, (cx + lado * 42, top + 8), (cx + lado * 50, top + 34), 1)
        pts = [(cx - 26, top - 5), (cx + 26, top - 5), (cx + 34, LH + 2), (cx - 34, LH + 2)]
        pygame.draw.polygon(s, P_SUETER, pts)
        for y in range(top + 3, LH, 4):                             # rayas del suéter
            w = 25 + (y - top) // 10
            rr(s, P_SUETER_S, cx - w, y, 2 * w + 1, 1)
        for y in range(top - 4, LH):                                # sombra tramada a la izquierda
            for x in range(cx - 25 - (y - top) // 10, cx - 8):
                if (x + y) & 1:
                    s.set_at((x, y), P_SUETER_O)
        pygame.draw.polygon(s, INK, pts, 1)

    def cuello(self, s, cx, hx, top, barbilla):
        rr(s, INK, hx - 14, barbilla - 8, 29, top - barbilla + 6)
        rr(s, P_PIEL, hx - 13, barbilla - 8, 27, top - barbilla + 6)
        for i in range(9):                                          # sombra tramada bajo la barbilla
            for x in range(hx - 13, hx + 14):
                if i < 4:
                    col = INK
                elif i < 7:
                    col = INK if (x + i) & 1 else P_PIEL_S
                else:
                    col = P_PIEL_S if (x + i) & 1 else P_PIEL
                s.set_at((x, barbilla + i), col)
        silueta(s, octogono(21, 12, 3), cx, top - 12, P_SUETER_S)   # cuello del suéter
        for x in range(cx - 18, cx + 19, 4):
            rr(s, INK, x, top - 10, 1, 8)

    # ---- pelo
    def pelo_atras(self, s, hx, hy, t, pan):
        for i, w in enumerate(octogono(43, 66, 14)):                # masa de pelo
            rr(s, INK, hx - w, hy - 55 + i, 2 * w + 1, 1)
        for lado in (-1, 1):                                        # patillas
            rr(s, INK, hx + lado * 40 - 4, hy - 12, 9, 38)
        tb = int(t * 12)
        k = 0.62 + 0.55 * pan                                       # erizado en pánico, caído en calma
        hcy = hy - 16
        for idx, (fr, L0, ao, ph, wd) in enumerate(self.pinchos):
            a = math.pi * 0.9 + fr * math.pi * 1.2
            bx, by = hx + 40 * math.cos(a), hcy + 40 * math.sin(a)
            ang = a + ao + ruido(idx + 99, tb) * 0.12 * pan + math.sin(t * 1.3 + ph) * 0.03
            L = L0 * (k + 0.05 * math.sin(t * 2.0 + ph)) + ruido(idx, tb) * 2.5 * pan
            nx, ny = -math.sin(ang), math.cos(ang)
            tri(s, INK, (bx + nx * wd, by + ny * wd),
                (bx + math.cos(ang) * L, by + math.sin(ang) * L),
                (bx - nx * wd, by - ny * wd))

    def flequillo_dibujar(self, s, hx, hy, t, pan):
        y0 = hy - 36
        rr(s, INK, hx - 41, hy - 48, 83, y0 - (hy - 48) + 1)
        tb = int(t * 12)
        for i, L in enumerate(self.flequillo):
            x = hx - 41 + i * 9
            L += int(round(ruido(i, tb) * 1.2 * pan))
            tri(s, INK, (x, y0), (x + 9, y0), (x + 4 + (i % 3 - 1), y0 + L))

    # ---- boca
    def boca(self, s, hx, my, w, h, esq):
        if h < 3:                                                   # cerrada, comisuras caídas
            rr(s, INK, hx - w // 2, my, w, 2)
            rr(s, INK, hx - w // 2, my + 2, 2, esq)
            rr(s, INK, hx + w // 2 - 2, my + 2, 2, esq)
            return
        silueta(s, octogono(w // 2, h, min(4, h // 3)), hx, my, INK)
        if h >= 8:
            rr(s, BLANCO, hx - w // 2 + 3, my + 1, w - 5, 2)        # dientes
        if h >= 11:
            rr(s, ROSA, hx - w // 4, my + h - 5, w // 2, 3)         # lengua

    # ---- ojo grande (octógono): párpado que baja, pupila cuadrada, ojera
    def ojo(self, s, ex, ey, op, lx, ly, pw, bolsa):
        hw, alto = 12, 25
        y0 = ey - alto // 2
        filas = octogono(hw, alto, 5)
        silueta(s, filas, ex, y0, BLANCO)
        if op > 0.06:
            px, py = ex + lx - pw // 2, ey + ly - pw // 2
            rr(s, INK, px, py, pw, pw)
            if pw >= 5:
                rr(s, BLANCO, px + 1, py + 1, 1, 1)
        cubre = int(round((1 - op) * 15))                           # filas tapadas por el párpado
        if cubre > 0:
            for i in range(1, cubre):
                w = filas[i] - 1
                rr(s, P_PIEL, ex - w, y0 + i, 2 * w + 1, 1)
            if op < 0.06:                                           # cerrado del todo
                for i in range(cubre + 1, alto - 1):
                    w = filas[i] - 1
                    rr(s, P_PIEL, ex - w, y0 + i, 2 * w + 1, 1)
            yl = y0 + cubre
            rr(s, INK, ex - filas[cubre], yl, 2 * filas[cubre] + 1, 1)
            if op < 0.75:                                           # párpado pesado: línea doble
                rr(s, INK, ex - filas[cubre + 1] + 1, yl + 1, 2 * filas[cubre + 1] - 1, 1)
            if op < 0.08:
                for dx in (-8, 0, 8):
                    rr(s, INK, ex + dx, yl + 2, 1, 2)
        if bolsa > 0.15:                                            # ojeras
            rr(s, P_OJERA, ex - 9, ey + 14, 19, 2)
            if bolsa > 0.5:
                rr(s, P_OJERA, ex - 7, ey + 16, 15, 2)
                rr(s, INK, ex - 8, ey + 18, 17, 1)

    # ---- dibujo completo
    def dibujar(self, canvas, t, e, dt, mundo):
        if self.spr is None:
            self.spr = pygame.Surface((LW, LH))
            self.spr.set_colorkey(CLAVE)
        s = self.spr
        s.fill(CLAVE)
        pan, cans, sus = e.panico, e.cansancio, e.suspiro
        tb = int(t * 14)                                            # el temblor avanza a saltos
        nod = self.cabeceo(t, cans)

        # respiración: corta y rápida en pánico, lenta y profunda en calma
        resp = int(round(math.sin(t * lerp(2.2, 11.0, pan)) * (1.0 + cans)))
        sx = int(round(ruido(1, tb) * 2.4 * pan))
        sy = int(round(ruido(2, tb) * 1.8 * pan))
        golpe = int(mundo.pulso * pan * 2)

        cx = LW // 2
        top = 175 - int(5 * pan) + resp + int(4 * cans) + int(3 * sus)    # hombros: tensos -> caídos
        hx = cx + sx + int(2 * cans)
        hy = 117 + sy - int(3 * pan) - golpe + int(5 * cans) + int(2 * sus) + int(7 * nod) + resp // 2

        # boca: grito en pánico, exhalación al soltar, línea caída cuando está cansado
        grito = pan * (0.55 + 0.45 * abs(math.sin(t * 8.5 + 0.7 * math.sin(t * 3.1))))
        o = max(grito, sus * 0.30)
        jaw = int(round(o * 10))
        mh = int(round(o * 22))
        mw = int(round(lerp(14, 32, pan)))

        self.cuerpo(s, cx, top)
        self.pelo_atras(s, hx, hy, t, pan)
        self.cuello(s, cx, hx, top, hy + 42 + jaw)
        for lado in (-1, 1):                                        # orejas
            ox = hx + lado * 40
            silueta(s, octogono(4, 15, 2), ox, hy - 2, P_PIEL)
            rr(s, P_PIEL_S, ox - 1, hy + 2, 3, 6)
        silueta(s, filas_cabeza(37, 42, 42 + jaw), hx, hy - 42, P_PIEL)

        # arrugas de las mejillas y nariz
        for lado in (-1, 1):
            for k in range(2):
                rr(s, INK, hx + lado * (20 + k * 5), hy + 14 + k * 2, 1, 9)
        rr(s, INK, hx + 2, hy + 6, 1, 8)
        rr(s, INK, hx, hy + 13, 3, 1)

        # ---- mirada: saltona en pánico, lenta y hacia abajo cuando está cansado
        self.t_mirada -= dt
        if self.t_mirada <= 0:
            self.t_mirada = lerp(random.uniform(1.4, 3.0), random.uniform(0.10, 0.30), pan)
            rg = lerp(2.0, 6.0, pan)
            self.destino = [random.uniform(-rg, rg),
                            random.uniform(-rg * 0.5, rg * 0.5) + 3.0 * cans * (1 - pan)]
        k = min(1.0, dt * lerp(2.5, 22.0, pan))
        self.mirada[0] += (self.destino[0] - self.mirada[0]) * k
        self.mirada[1] += (self.destino[1] - self.mirada[1]) * k
        pw = int(round(lerp(6, 3, pan)))                            # pupila diminuta en pánico
        mx = 12 - pw // 2 - 4
        lx = int(max(-mx, min(mx, self.mirada[0])))
        ly = int(max(-mx, min(mx, self.mirada[1])))

        # ---- párpados: desorbitados -> pesados, se cierran al suspirar y al cabecear
        op = lerp(1.0, 0.5 - 0.1 * math.sin(t * 0.9), cans)
        op *= 1.0 - 0.9 * nod
        op *= 1.0 - 0.97 * sus
        for lado in (-1, 1):
            self.ojo(s, hx + lado * 17, hy - 4, clamp01(op), lx, ly, pw, cans)

        self.flequillo_dibujar(s, hx, hy, t, pan)

        # ---- cejas: arqueadas de angustia -> bajas y planas
        by = hy - 21 - int(5 * pan) + int(3 * cans)
        for lado in (-1, 1):
            yi = by - int(8 * pan) - int(cans)
            yo = by + int(pan) + int(2 * cans)
            pygame.draw.line(s, INK, (hx + lado * 6, yi), (hx + lado * 30, yo), 3)

        self.boca(s, hx, hy + 20, mw, mh, 1 + int(2 * cans))

        # ---- sudor y marcas de temblor (solo en pánico)
        if pan > 0.25:
            for lado in (-1, 1):
                for i in range(3):
                    p = (t * 0.9 + i * 0.34 + (0.17 if lado > 0 else 0.0)) % 1.0
                    gota(s, hx + lado * (46 + 6 * i), hy - 32 + int(p * 52))
        if pan > 0.3 and tb % 2 == 0:
            for lado in (-1, 1):
                for j in range(3):
                    rr(s, P_BATA, hx + lado * (70 + 4 * j), hy - 12 + 5 * j, 1, 9)

        # ampliación sin suavizar: cada píxel del sprite pasa a ser PX x PX
        grande = pygame.transform.scale(s, (W, H))
        grande.set_colorkey(CLAVE)
        canvas.blit(grande, (0, 0))


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
    dur = 3.4
    for i in range(int(rate * dur)):
        tt = i / rate
        v = 0.0
        for k, f in enumerate((392.0, 329.63, 261.63, 196.0)):
            t0 = tt - k * 0.35
            if t0 > 0:
                v += (math.sin(TAU * f * t0) + 0.3 * math.sin(TAU * f * 2.01 * t0)) * math.exp(-t0 * 1.7)
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
            self.latido_t = 60.0 / lerp(54, 130, e.panico)   # taquicardia -> pulso lento
            self.pulso = 1.0
            latido = True
        self.pulso = max(0.0, self.pulso - dt * 3.5)
        # chispas de luz una vez que amanece
        if e.calma > 0.35:
            self.acum_luz += dt * 2.5 * e.calma
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
    bg = mix(GRIS_CRISIS, AZUL_CALMA, e.calma)
    bg = mix(bg, (255, 255, 255), mundo.pulso * 0.05 * e.panico)
    pygame.draw.rect(canvas, bg, (14, 34, W - 28, H - 48))
    canvas.blit(TRAZOS, (0, 0))
    if e.calma > 0.01:
        SOL.set_alpha(int(110 * e.calma))
        canvas.blit(SOL, (W - 560, -300))
    for en in ENTES:
        en.dibujar(canvas, t, e, dt, mundo, bg)
    mundo.dibujar_motas(canvas, "burbuja")
    if e.calma > 0.01:
        HACES.set_alpha(int(255 * smooth(0.05, 0.8, e.calma)))
        canvas.blit(HACES, (0, 0))
    pers.dibujar(canvas, t, e, dt, mundo)
    mundo.dibujar_motas(canvas, "luz")
    dibujar_espiral(canvas)


def postproceso(canvas, e, mundo, destino, con_grano=True, pixel=PIXEL):
    # Sin zoom suave: ampliar con suavizado deformaría la rejilla de píxeles del personaje.
    # El temblor de cámara usa desplazamientos enteros y solo existe mientras hay pánico.
    jit = int(round(3.5 * e.panico ** 1.5))
    ox = random.randint(-jit, jit) if jit else 0
    oy = random.randint(-jit, jit) if jit else 0
    destino.fill(PAPEL)
    destino.blit(canvas, (ox, oy))

    # capa de pixelado + tramado: rompe lo plano y da volumen con puntos de sombra y luz
    pixelar(destino, pixel)
    if pixel > 1 or CELDA > 1:
        sombra, luz = tramado(int(mundo.t * 6))
        destino.blit(sombra, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        destino.blit(luz, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    velo(destino, (8, 8, 14), 48 * e.panico)                  # penumbra de la crisis
    velo(destino, (120, 120, 128), 130 * e.gris)              # opacidad gris del principio
    VINETA.set_alpha(int(50 + 130 * e.panico))
    destino.blit(VINETA, (0, 0))

    if con_grano:
        grano().aplicar(destino, lerp(30, 54, e.panico), lerp(14, 30, e.panico))
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
        precalentar()

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

        imagen = pygame.transform.scale(self.frame, (self.ancho, self.alto))   # sin suavizar: conserva el pixel art
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
    fuentes_salida = {}

    def obtener_fuente_salida(familia, tamano):
        clave = (familia, tamano)
        if clave not in fuentes_salida:
            if familia is None:
                fuente = pygame.font.Font(None, tamano)
                fuente.set_bold(True)
            else:
                fuente = pygame.font.SysFont(familia, tamano, bold=True)
            fuentes_salida[clave] = fuente
        return fuentes_salida[clave]

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
            fuente = obtener_fuente_salida(
                "comicsansms", max(14, round(22 * escala_ui))
            )
        else:
            escala = min(ancho / W, alto / H)
            fuente = obtener_fuente_salida(
                None, max(18, round(26 * escala))
            )
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
    pygame.display.set_caption("Las voces - catarsis")
    precalentar()
    clock = pygame.time.Clock()
    mundo = Mundo()
    pers = Personaje()
    canvas = pygame.Surface((W, H))
    con_grano = True
    pixelado = PIXEL

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
                if ev.key == pygame.K_p:
                    pixelado = 1 if pixelado > 1 else PIXEL
                if ev.key == pygame.K_SPACE and mundo.t < T_CALMA - 0.5:
                    mundo.t = T_CALMA - 0.5
                if ev.key == pygame.K_m and latido:
                    sonido = not sonido
                    if not sonido:
                        murmullo.set_volume(0.0)

        e, hubo_latido = mundo.avanzar(dt)

        if latido and sonido:
            if hubo_latido:
                latido.set_volume(0.16 + 0.16 * e.panico)
                latido.play()
            murmullo.set_volume(0.03 + 0.5 * e.voces)
            if not mundo.campana and mundo.t >= T_CALMA + 0.6:
                mundo.campana = True
                campana.set_volume(0.45)
                campana.play()

        componer(canvas, e, dt, mundo, pers)
        postproceso(canvas, e, mundo, screen, con_grano, pixelado)

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