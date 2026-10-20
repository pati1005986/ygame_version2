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

El personaje usa el MISMO DISEÑO que PersonajeHumanoide (personaje.py): cabeza cuadrada, torso,
brazos y piernas de bloques con contorno oscuro grueso, paleta monocroma derivada de un solo color
(COLOR_PERSONAJE), ojos de 2-3 bloques con pupila de 1 bloque, pelo de mechones cuadrados, boca de
bloques, sombra de contacto y halo. Se dibuja en un lienzo pequeño y se amplía sin suavizar.
Mismas expresiones que en el juego: ojos desorbitados, sudor, temblor y rayitas de vibración en el
pánico; párpados pesados, ojeras, hombros caídos y pelo bajo al calmarse; y, al dormirse, moco que se
infla, baba y "zZz" (el cabeceo y el sobresalto se mantienen).

Fondo psicodélico en GRISES con píxeles gordos (como vacio.py): túnel en espiral con tramado de Bayer, rayas,
anillos poligonales, chispas, glitch y viñeta tramada, con palette cycling que se desboca con cada latido;
al calmarse se enfría hasta el azul y se aquieta.
Aura psicodélica (también gris): un túnel en espiral con tramado de Bayer y paleta rotatoria envuelve
al chico. En la desesperación cada parte de su cuerpo gira por bandas planas de gris, los ojos son
remolinos, deja ecos de color con cada latido y la imagen se parte en tiras (glitch). Al calmarse el color
se drena hasta su tono base, el aura se funde a azules suaves y todo se vuelve lento. Sin sonido.

Además lleva grano de película animado, polvo y rayones, una capa de pixelado y
un tramado (dither) de sombras y luces.

Requisitos:  pip install pygame

Controles:
  ESPACIO  -> saltar a la calma
  G        -> activar / quitar el grano
  P        -> activar / quitar el pixelado
  R        -> reiniciar
  ESC      -> salir

``AnimacionCatarsis`` permite reutilizar la escena como pantalla de transición
sin crear otra ventana ni interceptar los eventos del juego anfitrión.
"""
import colorsys
import math
import os
import random
import sys

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
    aura_base()
    tunel_base(0)
    tunel_base(1)
    tunel_vineta()


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
# Mismo diseño que PersonajeHumanoide (personaje.py): cabeza cuadrada, torso, brazos y piernas
# hechos con BLOQUES de rejilla y contorno oscuro grueso ("pocket cartoon"), paleta monocroma
# derivada de un solo color, ojos de 2-3 bloques con pupila de 1 bloque, pelo de mechones
# cuadrados y boca de bloques. Se dibuja en un lienzo pequeño (subceldas de SC píxeles de
# pantalla; una celda = 2 subceldas) y se amplía SIN suavizar.
SC = 12                                    # píxeles de pantalla por subcelda
LW, LH = 54, 75                            # lienzo del sprite en subceldas (648 x 900 px)
OFFX = (W - LW * SC) // 2                  # el lienzo es un poco más ancho que la pantalla
CLAVE = (255, 0, 255)                      # color transparente del sprite

# Color base del personaje: de él salen todos los tonos (igual que self.color en personaje.py).
# Cámbialo para pintar al chico de otro color.
COLOR_PERSONAJE = (190, 135, 110)

P_SUDOR = (190, 224, 255)
P_LAGRIMA = (126, 178, 238)
P_BURBUJA = (226, 240, 255)
P_VAHO = (240, 247, 255)
P_VAHO_O = (150, 184, 224)
BLANCO = (255, 255, 255)
BLANCO_OJO = (245, 245, 245)


def tono(color, factor):
    """Oscurece / aclara un color RGB (como _tono de personaje.py)."""
    return tuple(max(0, min(255, int(v * factor))) for v in color)


def bl(s, x, y, w, h, col):
    """Bloque en la rejilla del sprite (subceldas enteras)."""
    if w > 0 and h > 0:
        s.fill(col, (int(x), int(y), int(w), int(h)))


def blc(s, x, y, w, h, col, linea, g=1):
    """Bloque con contorno oscuro grueso (como _bloque_contorneado)."""
    bl(s, x - g, y - g, w + 2 * g, h + 2 * g, linea)
    bl(s, x, y, w, h, col)


def burbuja_sueno(s, x, y, r, linea):
    """Burbuja de moco: crece al inhalar y se encoge al exhalar."""
    if r < 2:
        return
    pygame.draw.circle(s, linea, (int(x), int(y)), int(r) + 1)
    pygame.draw.circle(s, P_BURBUJA, (int(x), int(y)), int(r))
    bl(s, x - r // 2, y - r // 2, 2, 1, BLANCO)
    bl(s, x - r // 2, y - r // 2, 1, 2, BLANCO)


def zeta(s, x, y, c, linea):
    """Una 'Z' de bloques de c subceldas por cuadro (el sueño)."""
    piezas = [(x, y, 4 * c, c), (x + 2 * c, y + c, c, c), (x + c, y + 2 * c, c, c), (x, y + 3 * c, 4 * c, c)]
    for px, py, pw, ph in piezas:                                   # contorno
        bl(s, px - 1, py - 1, pw + 2, ph + 2, linea)
    for px, py, pw, ph in piezas:
        bl(s, px, py, pw, ph, BLANCO)


# ------------------------------------------------------------------ aura psicodélica
# Túnel en espiral con tramado de Bayer detrás del chico (como vacio.py): un mapa de índices
# pintado con una paleta de bandas planas y línea oscura entre bandas, animado rotando la paleta
# ("palette cycling"). En la desesperación gira como loco y cambia de paleta a cada latido; al
# calmarse la paleta se funde a azules suaves y el giro se vuelve lento, casi un arrullo.
AW, AH = 108, 150                 # mapa en "píxeles gordos" de 6 px (= medio bloque del sprite)
AC = (54, 94)                     # centro del aura (a la altura del pecho del chico)
AURA_R = 50                       # radio del aura en píxeles gordos
AURA_K = 6                        # factor de ampliación (AW * 6 = 648 = ancho del lienzo del sprite)

_TEMAS_AURA = (                    # paletas de GRISES (se usan en el fondo y en el aura)
    # gris claro / medio / oscuro
    (((236, 236, 242), (122, 124, 134), (42, 42, 50), (192, 194, 202)), (8, 8, 12)),
    # alto contraste blanco y negro
    (((255, 255, 255), (24, 24, 28), (150, 152, 160), (64, 66, 74)), (0, 0, 0)),
    # gris frío
    (((204, 210, 222), (92, 98, 114), (152, 158, 172), (52, 56, 70)), (6, 8, 16)),
    # gris cálido
    (((216, 210, 202), (112, 106, 100), (72, 68, 66), (172, 166, 160)), (12, 10, 8)),
    # tablero: dos tonos
    (((246, 246, 248), (16, 16, 20)), (120, 120, 128)),
)


def crear_paleta(colores, separador, repeticiones=2):
    """256 colores: bandas planas, línea oscura al principio de cada banda y mitad final sombreada."""
    n = len(colores) * repeticiones
    ancho = 256.0 / n
    pal = []
    for i in range(256):
        banda = min(n - 1, int(i / ancho))
        pos = (i - banda * ancho) / ancho
        base = colores[banda % len(colores)]
        if pos < 0.12:
            col = separador
        elif pos < 0.62:
            col = base
        else:
            col = tuple(int(c * 0.72) for c in base)
        pal.append(col)
    return pal


PALETAS_AURA = tuple(crear_paleta(c, s) for c, s in _TEMAS_AURA)
PALETA_CALMA = crear_paleta(((70, 150, 255), (140, 200, 255), (40, 110, 230),
                             (190, 225, 255), (100, 110, 235)), (6, 34, 92))


PALETA_FONDO_CALMA = crear_paleta(((20, 114, 222), (34, 130, 236), (14, 98, 204), (52, 146, 240)),
                                  (8, 66, 150))


def neon(h, s=0.85, v=1.0):
    """Gris de banda plana (alterna claro / oscuro en 6 pasos según h). Mantiene el nombre de vacio.py,
    pero aquí la desesperación es monocroma: nada de arcoíris."""
    k = int(math.floor((h % 1.0) * 6)) % 6
    g = (255, 120, 215, 150, 235, 180)[k]
    return (g, g, min(255, g + 8))


def crear_mapa_aura():
    """Índices de paleta (1-255) de una espiral de 6 brazos con borde en pétalos y tramado de Bayer.
    El índice 0 es transparente."""
    cx, cy = AC
    datos = bytearray(AW * AH)
    k_ang = 6 / TAU
    i = 0
    for y in range(AH):
        dy = y - cy
        fila = BAYER[y & 3]
        for x in range(AW):
            dx = x - cx
            b = (fila[x & 3] + 0.5) / 16
            r = math.hypot(dx, dy)
            ang = math.atan2(dy, dx)
            limite = AURA_R * (1 + 0.07 * math.sin(8 * ang))
            if r <= limite * (0.80 + 0.20 * b):                     # borde desvanecido a cuadros
                lr = math.log(r + 1.0)
                u = k_ang * ang + 1.5 * lr + 0.10 * math.sin(3 * ang + 3.0 * lr) + (b - 0.5) * 0.03
                datos[i] = 1 + int((u % 1.0) * 254)
            i += 1
    return bytes(datos)


def aura_base():
    """Superficie indexada del aura (se crea una sola vez). False si esta versión de pygame no puede."""
    if "aura" not in _CACHE:
        datos = crear_mapa_aura()
        try:
            a = pygame.image.frombuffer(datos, (AW, AH), "P")
            a.set_colorkey(0)
        except (ValueError, TypeError, pygame.error):
            a = False
        _CACHE["aura_datos"] = datos                                # el buffer debe seguir vivo
        _CACHE["aura"] = a
    return _CACHE["aura"]


# ------------------------------------------------------------------ fondo psicodélico en grises
# Igual que vacio.py: todo se dibuja en una superficie diminuta (160 x 225) y se amplía x4 sin suavizar,
# así que cada punto del túnel es un píxel gordo de 4 px. Mapa de índices con tramado de Bayer, paleta de
# bandas planas con línea oscura y palette cycling; rayas oscuras, anillos poligonales, chispas que caen
# hacia el centro, tiras de glitch en cada latido y viñeta tramada. Al calmarse la paleta se enfría
# hasta el azul de la calma y casi todo el movimiento se apaga.
TW, TH, TK = 160, 225, 4
TC = (80, 141)                    # punto de fuga: el pecho del chico (320, 564 px)
RMAX = math.hypot(80, 141)
TRIM = pygame.Rect(14, 34, W - 28, H - 48)
ANILLOS = ((255, 255, 255), (196, 198, 208), (120, 122, 132), (238, 238, 242))
VINETA_TONOS = ((34, 34, 44), (14, 14, 20), (0, 0, 0))


def crear_mapa_tunel(variante):
    """Espiral con tramado de Bayer. variante 0: 6 brazos; variante 1: 4 brazos, giro contrario."""
    if variante == 0:
        brazos, torsion, alabeo, lobulos = 6, 1.5, 0.10, 3
    else:
        brazos, torsion, alabeo, lobulos = 4, -1.2, 0.17, 5
    cx, cy = TC
    k_ang = brazos / TAU
    datos = bytearray(TW * TH)
    i = 0
    for y in range(TH):
        dy = y - cy
        fila = BAYER[y & 3]
        for x in range(TW):
            dx = x - cx
            ang = math.atan2(dy, dx)
            lr = math.log(math.hypot(dx, dy) + 1.0)
            u = k_ang * ang + torsion * lr + alabeo * math.sin(lobulos * ang + 3.0 * lr)
            u += ((fila[x & 3] + 0.5) / 16 - 0.5) * 0.03            # bordes de banda "a cuadros"
            datos[i] = int((u % 1.0) * 256)
            i += 1
    return bytes(datos)


def tunel_base(variante):
    """Superficie indexada del túnel (una por variante). False si pygame no admite el formato."""
    clave = "tun%d" % variante
    if clave not in _CACHE:
        datos = crear_mapa_tunel(variante)
        try:
            sup = pygame.image.frombuffer(datos, (TW, TH), "P")
        except (ValueError, TypeError, pygame.error):
            sup = False
        _CACHE[clave + "_datos"] = datos                            # el buffer debe seguir vivo
        _CACHE[clave] = sup
    return _CACHE[clave]


def tunel_vineta():
    """Viñeta de 3 tonos con tramado de Bayer (sin degradados suaves), ya ampliada."""
    if "tun_vin" not in _CACHE:
        peq = pygame.Surface((TW, TH))
        peq.fill(CLAVE)
        cx, cy = TW / 2, TH / 2
        rmax = math.hypot(cx, cy)
        for y in range(TH):
            fila = BAYER[y & 3]
            for x in range(TW):
                d = math.hypot(x - cx, y - cy) / rmax
                borde = clamp01((d - 0.5) / 0.5)
                borde = borde * borde * (3 - 2 * borde)
                nivel = min(3, int(0.75 * borde * 3 + (fila[x & 3] + 0.5) / 16))
                if nivel:
                    peq.set_at((x, y), VINETA_TONOS[nivel - 1])
        grande = pygame.transform.scale(peq, (TW * TK, TH * TK))
        grande.set_colorkey(CLAVE)
        _CACHE["tun_vin"] = grande
    return _CACHE["tun_vin"]


class Fondo:
    """Estado del túnel de fondo (se reinicia con el mundo)."""

    def __init__(self):
        self.fase = random.uniform(0, 255)
        self.giro = random.uniform(0, TAU)
        self.anillos = random.random()
        self.chispas = [[random.uniform(0, TAU), RMAX * random.uniform(0.08, 1.2), random.randrange(4)]
                        for _ in range(40)]
        self.glitch = 0.0
        self.tiras = []
        self.lat_visto = -1
        self.variante = 0
        self.tema = 0

    def dibujar(self, canvas, t, e, dt, mundo):
        """Pinta el túnel sobre la hoja. Devuelve False si no se pudo (entonces se usa el fondo plano)."""
        pan, cm = e.panico, e.calma
        if pan > 0.3:                                               # al calmarse ya no cambia de forma
            self.variante = ((mundo.latidos + 2) // 4) % 2
            self.tema = (mundo.latidos // 2) % len(PALETAS_AURA)
        base = tunel_base(self.variante)
        if not base:
            return False

        self.fase += (14 + 300 * pan + 450 * mundo.pulso * pan) * dt
        self.giro += (0.3 + 2.2 * pan) * dt
        self.anillos += (0.1 + 1.0 * pan) * dt

        pal = PALETAS_AURA[self.tema]
        oscuro = _TEMAS_AURA[self.tema][1]
        if cm > 0.01:                                               # el gris se enfría hasta el azul
            pal = [mix(a, b, cm) for a, b in zip(pal, PALETA_FONDO_CALMA)]
            oscuro = mix(oscuro, (8, 66, 150), cm)
        corte = int(self.fase) % 256
        base.set_palette(pal[corte:] + pal[:corte])                 # palette cycling

        peq = _CACHE.get("tun_peq")
        if peq is None:
            peq = _CACHE["tun_peq"] = pygame.Surface((TW, TH))
            _CACHE["tun_gr"] = pygame.Surface((TW * TK, TH * TK))
        gr = _CACHE["tun_gr"]
        peq.blit(base, (0, 0))
        cx, cy = TC
        cos, sin = math.cos, math.sin
        paso = int(t * 20)

        if pan > 0.3:
            r0, r1 = RMAX * 0.08, RMAX * 1.1                        # rayas de velocidad oscuras
            for k in range(12):
                a = -self.giro * 0.5 + k * TAU / 12
                pygame.draw.line(peq, oscuro, (int(cx + cos(a) * r0), int(cy + sin(a) * r0)),
                                 (int(cx + cos(a) * r1), int(cy + sin(a) * r1)), 2 if k % 3 == 0 else 1)
        if pan > 0.25:
            for k in range(6):                                      # anillos poligonales que se cierran
                f = (self.anillos + k / 6.0) % 1.0
                r = RMAX * 1.1 * (1.0 - f) ** 2.2
                if r < 3:
                    continue
                lados = (4, 6, 8, 4, 6, 8)[k]
                a0 = self.giro * (1.0 + 0.15 * k) * (1 if k % 2 else -1)
                pts = [(int(cx + cos(a0 + TAU * i / lados) * r), int(cy + sin(a0 + TAU * i / lados) * r))
                       for i in range(lados)]
                pygame.draw.polygon(peq, ANILLOS[(k * 3 + paso // 3) % 4], pts, 2 if r > RMAX * 0.3 else 1)

        # chispas que se precipitan al centro (siempre se mueven; solo se ven en pánico)
        kk = math.exp(-(1.4 + pan) * dt)
        gc = (0.5 + 0.8 * pan) * dt
        lejos, medio = RMAX * 0.55, RMAX * 0.28
        for c in self.chispas:
            c[0] += gc
            c[1] *= kk
            if c[1] < RMAX * 0.07:
                c[0] = random.uniform(0, TAU)
                c[1] = RMAX * random.uniform(0.9, 1.2)
                c[2] = random.randrange(4)
            if pan > 0.2:
                ang, r, ci = c
                col = ANILLOS[(ci + paso // 2) % 4]
                x, y = int(cx + cos(ang) * r), int(cy + sin(ang) * r)
                rc = r * 1.22
                pygame.draw.line(peq, col, (int(cx + cos(ang - 0.10) * rc), int(cy + sin(ang - 0.10) * rc)), (x, y))
                if r > lejos:
                    peq.fill((255, 255, 255), (x - 1, y, 3, 1))
                    peq.fill((255, 255, 255), (x, y - 1, 1, 3))
                elif r > medio:
                    peq.fill(col, (x, y, 2, 2))
                elif 0 <= x < TW and 0 <= y < TH:
                    peq.set_at((x, y), (255, 255, 255))

        # glitch: tiras desplazadas en cada latido
        if pan > 0.3 and mundo.latidos != self.lat_visto:
            self.lat_visto = mundo.latidos
            self.glitch = 0.12
            self.tiras = [(random.randrange(TH), random.randint(2, 7), random.choice((-1, 1)) * random.randint(3, 12))
                          for _ in range(random.randint(2, 5))]
        self.glitch = max(0.0, self.glitch - dt)
        if self.glitch > 0 and self.tiras:
            tmp = peq.copy()
            for y0, alto, dx in self.tiras:
                peq.blit(tmp, (dx, y0), pygame.Rect(0, y0, TW, alto))

        pygame.transform.scale(peq, (TW * TK, TH * TK), gr)        # ampliar sin suavizar
        canvas.set_clip(TRIM)
        canvas.blit(gr, (0, 0))
        vin = tunel_vineta()
        vin.set_alpha(int(255 * (0.3 + 0.7 * pan)))
        canvas.blit(vin, (0, 0))
        canvas.set_clip(None)
        return True


# ------------------------------------------------------------------ personaje (índices de tonos)
BR, CL, BA, PS, OS, MO, BO = range(7)      # brillo, claro, base, piel en sombra, oscuro, muy oscuro, bolsa


class Personaje:
    def __init__(self):
        self.mirada = (1, 1)
        self.t_mirada = 0.0
        self.spr = None
        self.out = None
        self.parp = 0.0                                             # progreso del parpadeo actual
        self.t_parp = 2.0                                           # tiempo hasta el siguiente
        self.zzz = 0.0                                              # cuánto se ve el sueño (suavizado)
        self.sombra = None
        self.halo = None
        self.fase = random.uniform(0, 255)                          # fase de la paleta del aura
        self.glitch = 0.0
        self.tiras = []
        self.lat_visto = -1

    @staticmethod
    def cabeceo(t, cans):
        """0 -> 1: la cabeza se va cayendo de sueño y se levanta de golpe."""
        if cans < 0.5:
            return 0.0
        ph = (t - 12.0) % 7.0
        return cans * smooth(0.4, 3.2, ph) * (1.0 - smooth(3.2, 3.45, ph))

    @staticmethod
    def sobresalto(t, cans):
        """0 -> 1 -> 0: al levantar la cabeza de golpe abre los ojos de par en par."""
        if cans < 0.5:
            return 0.0
        ph = (t - 12.0) % 7.0
        return cans * smooth(3.15, 3.3, ph) * (1.0 - smooth(3.4, 4.3, ph))

    # ---- aura: el túnel psicodélico que lo envuelve (detrás de las voces y del chico)
    def dibujar_aura(self, canvas, t, e, dt, mundo):
        pan = e.panico
        self.fase += (24 + 240 * pan + 420 * mundo.pulso * pan) * dt      # el latido da un tirón
        base = aura_base()
        if not base:
            return
        alfa = smooth(0.0, 1.0, t) * (190 * pan + 90 * (1.0 - pan) * (0.75 + 0.25 * math.sin(t * 0.9)))
        if alfa < 4:
            return
        pal = PALETAS_AURA[(mundo.latidos // 2 + 2) % len(PALETAS_AURA)]   # otra paleta que el fondo
        if e.calma > 0.01:
            pal = [mix(a, b, e.calma) for a, b in zip(pal, PALETA_CALMA)]  # se funde a azules
        resto = pal[1:]
        k = int(self.fase) % 255
        base.set_palette([pal[0]] + resto[k:] + resto[:k])                 # palette cycling

        peq = _CACHE.get("aura_peq")
        if peq is None:
            peq = _CACHE["aura_peq"] = pygame.Surface((AW, AH))
            gr = _CACHE["aura_gr"] = pygame.Surface((AW * AURA_K, AH * AURA_K))
            gr.set_colorkey(CLAVE)
        gr = _CACHE["aura_gr"]
        peq.fill(CLAVE)
        peq.blit(base, (0, 0))
        if pan > 0.2:                                                      # anillos poligonales que se cierran
            for k2 in range(4):
                f = (t * 0.55 + k2 / 4.0) % 1.0
                r = AURA_R * 0.95 * (1.0 - f) ** 1.6
                if r < 3:
                    continue
                lados = (4, 6, 8, 4)[k2]
                a0 = t * (1.0 + 0.2 * k2) * (1 if k2 % 2 else -1)
                pts = [(AC[0] + math.cos(a0 + TAU * i / lados) * r,
                        AC[1] + math.sin(a0 + TAU * i / lados) * r) for i in range(lados)]
                pygame.draw.polygon(peq, neon(t * 0.8 + k2 / 4.0), pts, 1)
        pygame.transform.scale(peq, (AW * AURA_K, AH * AURA_K), gr)
        gr.set_alpha(int(min(255, alfa)))
        canvas.blit(gr, (OFFX, 0))

    # ---- pelo: mechones cuadrados de 1 celda de ancho (erizados en pánico, bajos en calma)
    def pelo(self, s, hx, hy, t, pan, cans, colores, cuadro):
        if pan > 0.5:
            bordes = (-7, -4, -1, 2, 5)
            altos = [2 + ((cuadro + i) * 7) % 3 for i in range(5)]
            viento = (((cuadro * 5) % 3) - 1) * 0.8
        else:
            bordes = (-5, -1, 3)
            altos = [1, 2, 1]
            viento = 0.0
        for i, bx in enumerate(bordes):
            color = colores[i % len(colores)]
            alto = 1 + int(round((altos[i] - 1) * pan))
            if pan <= 0.5:
                alto = max(1, int(round(lerp(altos[i], 1, cans))))   # el pelo se baja
            mece = math.sin(t * 1.4 + i * 0.8) * (1.0 - pan) * 1.2   # mecha que se mece en calma
            for nivel in range(alto):
                des = int(round(viento * nivel * 1.5 + mece * nivel))
                bl(s, hx + bx + des, hy - (nivel + 1) * 2, 2, 2, color)

    # ---- ojo: bloque blanco n x n celdas, pupila de 1 celda, párpado que baja
    #      hip = (cuadro, color vivo, tinta): en pánico la pupila se vuelve una espiral hipnótica
    def ojo(self, s, ex, ey, n, op, mx, my, lado, pan, claro, linea, hip=None):
        es = 2 * n
        bl(s, ex, ey, es, es, BLANCO_OJO)
        c = max(0, min(n, int(round((1.0 - op) * n))))              # filas tapadas por el párpado
        if pan > 0.5 and c == 0 and hip is None:                    # venitas del ojo desorbitado
            xv = ex if lado < 0 else ex + es - 1
            bl(s, xv, ey + 1, 1, 1, ROSA)
            bl(s, xv, ey + es - 2, 1, 1, ROSA)
        if c < n:
            if hip is not None and n == 3 and c == 0:
                anillo = ((0, 0), (1, 0), (2, 0), (2, 1), (2, 2), (1, 2), (0, 2), (0, 1))
                paso = (hip[0] // 2) % 8
                if lado > 0:
                    paso = -paso                                    # el otro ojo gira al revés
                for j, (a, b) in enumerate(anillo):
                    d = (j - paso) % 8
                    col = hip[1] if d < 2 else (hip[2] if d < 4 else BLANCO_OJO)
                    bl(s, ex + a * 2, ey + b * 2, 2, 2, col)
                bl(s, ex + 2, ey + 2, 2, 2, hip[2])                 # centro del remolino
            else:
                pc = 0 if mx < 0 else (n - 1 if mx > 0 else (n - 1) // 2)
                pr = 0 if my < 0 else (n - 1 if my > 0 else (n - 1) // 2)
                pr = max(pr, c)
                bl(s, ex + pc * 2, ey + pr * 2, 2, 2, linea)        # pupila de 1 bloque
        if c >= 1:
            for r in range(c - 1):
                bl(s, ex, ey + r * 2, es, 2, claro)
            bl(s, ex, ey + (c - 1) * 2, es, 2, linea)               # línea del párpado

    # ---- dibujo completo
    def dibujar(self, canvas, t, e, dt, mundo):
        if self.spr is None:
            self.spr = pygame.Surface((LW, LH))
            self.spr.set_colorkey(CLAVE)
            self.out = pygame.Surface((LW, LH))
            self.out.set_colorkey(CLAVE)
        s = self.spr
        s.fill(CLAVE)
        pan, cans, sus = e.panico, e.cansancio, e.suspiro
        nod = self.cabeceo(t, cans)
        sob = self.sobresalto(t, cans)
        tb = int(t * 14)                                            # el temblor avanza a saltos
        cuadro = int(t * 14.3)                                      # ~70 ms, como el pelo de personaje.py

        # ---- paleta: en pánico cada parte del cuerpo gira por el arcoíris en bandas planas (cada una
        # con su desfase); al calmarse todo se funde de nuevo al color base del chico.
        C0 = COLOR_PERSONAJE
        psy = 0.9 * pan
        deriva = t * 0.22
        m = 1.0 + 0.05 * (int(t * 11) % 3) * pan                    # "chisporroteo" en 3 pasos

        def tonos(off):
            Cp = mix(C0, neon(deriva + off), psy)
            return (tono(Cp, 1.75 * m), tono(Cp, 1.45 * m), tono(Cp, 1.0 * m), tono(Cp, 1.2 * m),
                    tono(Cp, 0.62), tono(Cp, 0.35), tono(Cp, 0.72))

        cab, tor, bra, pie_c = tonos(0.0), tonos(0.33), tonos(0.66), tonos(0.16)
        contorno = mix(tono(C0, 0.16), (10, 0, 26), psy)
        claro, brillo, piel_s, bolsa = cab[CL], cab[BR], cab[PS], cab[BO]

        # parpadeo: rápido y nervioso en pánico, lento y espaciado en calma
        self.t_parp -= dt
        if self.t_parp <= 0:
            self.parp = 0.16
            self.t_parp = lerp(random.uniform(2.2, 5.0), random.uniform(0.5, 1.4), pan)
        blink = 0.0
        if self.parp > 0:
            self.parp = max(0.0, self.parp - dt)
            blink = math.sin(math.pi * (1.0 - self.parp / 0.16)) * lerp(1.0, 0.55, pan)

        # ---- posición: respiración, temblor, latido, hombros caídos y balanceo
        resp = int(round(math.sin(t * lerp(2.2, 11.0, pan)) * (0.5 + 0.5 * cans + 0.5 * pan)))
        sx = int(round(ruido(1, tb) * 1.3 * pan))
        sy = int(round(ruido(2, tb) * 1.3 * pan))
        golpe = int(round(mundo.pulso * pan))
        bal = int(round(math.sin(t * 0.6) * 1.2 * cans * (1.0 - nod)))
        caida = int(round(2 * cans)) + int(round(sus))
        cx = 27 + sx + bal
        pie = 68
        torso_h = 12 - caida
        torso_y = pie - 12 - torso_h + sy - resp
        hx = cx
        hy = torso_y - 12 - golpe + int(round(4 * nod)) + int(round(sus)) - int(round(sob))

        # ---- boca: grito en pánico, exhalación al soltar, línea caída (y floja al dormirse)
        grito = pan * (0.55 + 0.45 * abs(math.sin(t * 8.5 + 0.7 * math.sin(t * 3.1))))
        o = max(grito, sus * 0.55, nod * 0.35, sob * 0.5)
        abre = int(round(o * 5))                                    # alto de la boca abierta
        n = 3 if (pan > 0.5 or sob > 0.5) else 2                    # ojos desorbitados o normales
        mt = 10 + (1 if n == 3 else 0)                              # fila donde empieza la boca
        head_h = max(12, mt + abre + 2) if abre >= 2 else 12        # la mandíbula se descuelga

        # ---- piernas (bloques oscuros) y pies
        tembla = int(round(ruido(4, tb) * pan))
        for lado in (-1, 1):
            lx = (cx - 6 if lado < 0 else cx + 2) + (tembla if lado < 0 else -tembla)
            blc(s, lx, pie - 14, 4, 12, pie_c[OS], contorno)
            fx = cx - 8 if lado < 0 else cx + 2
            blc(s, fx + (tembla if lado < 0 else -tembla), pie - 2, 6, 2, pie_c[MO], contorno)

        # ---- torso con cinturón y sombra en el lado contrario a la luz
        blc(s, cx - 7, torso_y, 14, torso_h, tor[BA], contorno)
        bl(s, cx - 7, torso_y, 2, torso_h, tor[OS])
        bl(s, cx - 7, torso_y + torso_h - 2, 14, 2, tor[MO])
        bl(s, cx - 1, torso_y + torso_h - 2, 2, 2, tor[CL])

        # ---- brazos: arriba y agitándose en pánico, colgando y cansados en calma
        ag = (math.sin(t * 17.0), math.sin(t * 17.0 + 2.4))
        fuera = int(round(pan * 2))
        for k, lado in enumerate((-1, 1)):
            lev = int(round(pan * (6 + 3 * ag[k])))
            col = int(round(math.sin(t * 0.6 + (0.0 if lado < 0 else math.pi)) * cans * (1.0 - nod)))
            ay = torso_y + 1 - lev + col
            ax = cx - 11 - fuera if lado < 0 else cx + 7 + fuera
            blc(s, ax, ay, 4, 10, bra[CL], contorno)
            bl(s, ax, ay + 8, 4, 2, bra[OS])

        # ---- cabeza cuadrada
        blc(s, hx - 6, hy, 12, head_h, claro, contorno)
        bl(s, hx - 6, hy, 2, head_h, piel_s)                        # mejilla en sombra
        bl(s, hx - 6, hy + head_h - 2, 12, 2, piel_s)               # sombra de la barbilla
        bl(s, hx + 2, hy + 1, 4, 1, brillo)                         # brillo (luz arriba a la derecha)
        pelos = [mix(contorno, neon(deriva * 2 + i / 5.0), psy) for i in range(5)]   # mechones de colores
        self.pelo(s, hx, hy, t, pan, cans, pelos, cuadro)

        # ---- mirada: nerviosa de lado a lado en pánico, lenta y hacia abajo cuando está cansado
        self.t_mirada -= dt
        if self.t_mirada <= 0:
            self.t_mirada = lerp(random.uniform(1.4, 3.0), random.uniform(0.10, 0.30), pan)
            self.mirada = (random.choice((-1, 1)), 1 if cans * (1 - pan) > 0.3 else random.choice((0, 1)))
        if pan > 0.5:
            mx, my = (-1, 0, 1, 0)[int(t * 11) % 4], 0
        else:
            mx, my = self.mirada

        # ---- párpados: desorbitados -> pesados; se cierran al suspirar, parpadear y cabecear
        op = lerp(1.0, 0.5 - 0.1 * math.sin(t * 0.9), cans)
        op *= 1.0 - 0.9 * nod
        op = op + (1.0 - op) * 0.85 * sob                           # sobresalto al despertar de golpe
        op *= 1.0 - 0.97 * sus
        op *= 1.0 - blink
        op = clamp01(op)
        es = 2 * n
        ey = hy + 4
        for lado in (-1, 1):
            if n == 3:
                ex = hx - 8 if lado < 0 else hx + 2                 # los ojos sobresalen de la cabeza
            else:
                ex = hx - 6 if lado < 0 else hx + 2
            hip = None
            if pan > 0.5 and n == 3:                                # ojos de remolino
                hip = (cuadro, neon(deriva * 2.5 + (0.0 if lado < 0 else 0.5)), contorno)
            self.ojo(s, ex, ey, n, op, mx, my, lado, pan, claro, contorno, hip)
            if cans > 0.15:                                         # ojeras
                bl(s, ex, ey + es, es, 2, bolsa)
                if cans > 0.6:
                    bl(s, ex + 1, ey + es + 2, es - 2, 1, bolsa)
            if pan > 0.3 or sob > 0.3:                              # cejas: angustia / sobresalto
                tic = int(round(ruido(3 + lado, tb) * pan))
                alza = 2 if sob > 0.3 else 0
                mitad = es // 2
                x_ext = ex if lado < 0 else ex + es - mitad
                x_int = ex + es - mitad if lado < 0 else ex
                inclina = 2 if pan > 0.3 else 0
                bl(s, x_ext, ey - 2 - tic - alza, mitad, 2, contorno)
                bl(s, x_int, ey - 2 - inclina - tic - alza, mitad, 2, contorno)

        # ---- boca
        if abre >= 2:
            mw = int(round(lerp(4, 8, pan)))
            mx0 = hx - mw // 2
            bl(s, mx0, hy + mt, mw, abre, contorno)
            if abre >= 4:
                bl(s, mx0 + 1, hy + mt, mw - 2, 2, BLANCO)          # dientes
            if abre >= 5:
                bl(s, mx0 + 2, hy + mt + abre - 2, mw - 4, 2, ROSA)  # lengua
        else:
            bl(s, hx - 3, hy + 9, 6, 2, contorno)                   # línea cansada
            if cans > 0.4:
                bl(s, hx - 3, hy + 11, 1, 1, contorno)              # comisuras caídas
                bl(s, hx + 2, hy + 11, 1, 1, contorno)

        # ---- sudor, lágrimas y rayitas de vibración (solo en pánico)
        if pan > 0.25:
            for lado in (-1, 1):
                for i in range(2):
                    p = (t * 0.9 + i * 0.5 + (0.17 if lado > 0 else 0.0)) % 1.0
                    gx = hx + lado * (9 + 2 * i) - 1
                    gy = hy - 4 + int(p * 26)
                    blc(s, gx, gy, 2, 3, P_SUDOR, contorno)
                    bl(s, gx, gy + 1, 1, 1, BLANCO)
        if pan > 0.6:                                               # lloro de angustia
            for lado in (-1, 1):
                ex = hx - 8 if lado < 0 else hx + 2
                for j in range(2):
                    p = (t * 1.3 + j * 0.5 + (0.25 if lado > 0 else 0.0)) % 1.0
                    bl(s, ex + 2, ey + 6 + int(p * 14), 2, 3, P_LAGRIMA)
        if pan > 0.3:
            for i, g in enumerate((-160, -130, -50, -20, 10, 170)):
                if (cuadro + i) % 3 == 0:
                    continue
                a = math.radians(g)
                k = (cuadro + i) % 2
                x = hx + math.cos(a) * (11 + 2 * k)
                y = hy + 6 + math.sin(a) * (10 + 2 * k)
                vib = mix(contorno, neon(deriva * 3 + i / 6.0), psy)  # chispas de vibración de colores
                if abs(math.cos(a)) > abs(math.sin(a)):
                    bl(s, x - 2, y, 4, 2, vib)
                else:
                    bl(s, x, y - 2, 2, 4, vib)

        # ---- el alivio: una lágrima que resbala despacio y una bocanada de aire
        u = (t - 7.6) / 3.8
        if 0.0 < u < 1.0 and sus > 0.02:
            lx = hx - 6 + 1
            largo = int(u * 14)
            bl(s, lx, ey + es, 2, largo, P_LAGRIMA)
            bl(s, lx - 1, ey + es + largo, 4, 2, P_LAGRIMA)
            bl(s, lx, ey + es + largo, 1, 1, BLANCO)
        u = (t - 7.7) / 2.8
        if 0.0 < u < 1.0:
            bolas = []
            for i in range(5):                                      # sale de la boca y se abre hacia abajo
                pu = clamp01(u * 1.4 - i * 0.1)
                if pu <= 0.0:
                    continue
                r = 2 + int(pu * 3) - (1 if pu > 0.85 else 0)
                bolas.append((hx + (i - 2) * int(3 + pu * 4) - r // 2,
                              hy + mt + 6 + int(pu * 12) + (i % 2) * 2, r))
            for x, y, r in bolas:
                bl(s, x - 1, y - 1, r + 2, r + 2, P_VAHO_O)
            for x, y, r in bolas:
                bl(s, x, y, r, r, P_VAHO)
            for x, y, r in bolas[:2]:
                bl(s, x, y, 1, 1, BLANCO)

        # ---- se duerme: moco que se infla, baba y zZz
        dormido = nod > 0.3 and sob < 0.05
        self.zzz += ((1.0 if dormido else 0.0) - self.zzz) * min(1.0, dt * (3.0 if dormido else 14.0))
        z = self.zzz
        if z > 0.15:
            infla = 0.5 + 0.5 * math.sin(t * 1.7)
            r = int(2 + 5 * infla * z)
            burbuja_sueno(s, hx + 6 + r, hy + 9 + r // 3, r, contorno)
            largo = int(z * (4 + 2 * abs(math.sin(t * 1.2))))
            bl(s, hx, hy + head_h, 2, largo, P_BURBUJA)             # baba
            for i in range(3):
                p = (t * 0.5 + i / 3.0) % 1.0
                zeta(s, hx + 9 + int(i * 3 + p * 6), hy - 6 - int(p * 22), 1 + i // 2, contorno)

        # ---- psicodelia final: ecos de color (aberración cromática en cada latido) y glitch en tiras.
        # Todo se apaga solo cuando el pánico se suelta.
        out = self.out
        out.fill(CLAVE)
        if pan > 0.15:
            try:
                mascara = pygame.mask.from_surface(s)
                sep = int(round(pan * (1.0 + 2.2 * mundo.pulso) * 1.3))
                if sep >= 1:
                    for k, (gx, gy) in enumerate(((-1, 0), (1, 0), (0, -1))):
                        sil = mascara.to_surface(setcolor=neon(deriva * 1.6 + k / 3.0, 0.9) + (255,),
                                                 unsetcolor=(0, 0, 0, 0))
                        out.blit(sil, (gx * sep, gy * sep))
            except (AttributeError, TypeError, ValueError, pygame.error):
                pass
        out.blit(s, (0, 0))
        if pan > 0.3 and mundo.latidos != self.lat_visto:           # glitch: tiras desplazadas en cada latido
            self.lat_visto = mundo.latidos
            self.glitch = 0.12
            self.tiras = [(random.randrange(LH), random.randint(1, 4), random.choice((-1, 1)) * random.randint(2, 6))
                          for _ in range(random.randint(2, 5))]
        self.glitch = max(0.0, self.glitch - dt)
        if self.glitch > 0 and self.tiras:
            tmp = out.copy()
            for y0, alto, dx in self.tiras:
                out.fill(CLAVE, (0, y0, LW, alto))
                out.blit(tmp, (dx, y0), pygame.Rect(0, y0, LW, alto))

        # ---- sombra de contacto y halo (como en personaje.py), y ampliación sin suavizar
        cx_px = OFFX + 27 * SC
        if self.sombra is None:
            self.sombra = pygame.Surface((300, 44), pygame.SRCALPHA)
            pygame.draw.ellipse(self.sombra, (0, 0, 0, 110), self.sombra.get_rect())
        canvas.blit(self.sombra, self.sombra.get_rect(center=(cx_px, (pie + 1) * SC + 4)))
        if self.halo is None:
            self.halo = pygame.Surface((560, 720), pygame.SRCALPHA)
            h_claro, h_brillo = tono(C0, 1.45), tono(C0, 1.75)
            for (col, a, grosor, inset) in ((h_claro, 15, 14, 8), (h_claro, 25, 9, 40), (h_brillo, 28, 5, 76)):
                pygame.draw.ellipse(self.halo, col + (a,), (inset, inset, 560 - 2 * inset, 720 - 2 * inset), grosor)
        pulso_halo = 0.78 + 0.22 * math.sin(t * 1.5)
        self.halo.set_alpha(int(255 * (0.35 + 0.65 * e.calma) * pulso_halo))
        canvas.blit(self.halo, self.halo.get_rect(center=(cx_px, 560)))

        grande = pygame.transform.scale(out, (LW * SC, LH * SC))
        grande.set_colorkey(CLAVE)
        canvas.blit(grande, (OFFX, 0))


# ------------------------------------------------------------------ mundo
class Mundo:
    def __init__(self):
        self.reiniciar()

    def reiniciar(self):
        self.t = 0.0
        self.motas = []
        self.latido_t = 0.4
        self.pulso = 0.0
        self.latidos = 0
        self.fondo = Fondo()
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
            self.latidos += 1
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
    if not mundo.fondo.dibujar(canvas, t, e, dt, mundo):
        canvas.blit(TRAZOS, (0, 0))
    if e.calma > 0.01:
        SOL.set_alpha(int(50 * e.calma))
        canvas.blit(SOL, (W - 560, -300))
    pers.dibujar_aura(canvas, t, e, dt, mundo)
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
    velo(destino, (120, 120, 128), 60 * e.gris)              # opacidad gris del principio
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
    pygame.display.init()          # solo vídeo: no se abre ningún dispositivo de audio
    pygame.font.init()
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

        e, _ = mundo.avanzar(dt)
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