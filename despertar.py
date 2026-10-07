"""
Cara a carboncillo -> pixel art 100% procedural (pygame + numpy)
No carga ninguna imagen: todo el dibujo se construye con formas y trazos en código.

    pip install pygame numpy
    python carboncillo_procedural.py

Controles:
    S       guardar un fotograma PNG (pequeño y ampliado)
    ESC     salir

La animación alterna niveles, semilla, dithering y grano en un ciclo de 10 segundos.
"""
import numpy as np
import pygame
from math import comb

# ----------------------------------------------------------------------------
# Lienzo
# ----------------------------------------------------------------------------
W, H = 160, 184            # resolución real del pixel art
SCALE = 5                  # ampliación en pantalla
A = W / H                  # relación de aspecto (para trazos redondos)

V, U = np.mgrid[0:H, 0:W]
U = (U + 0.5) / W          # 0..1 horizontal
V = (V + 0.5) / H          # 0..1 vertical
X = U * A                  # horizontal corregida (mismas unidades que V)

BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6],
                   [3, 11, 1, 9], [15, 7, 13, 5]], dtype=np.float32) / 16.0 - 0.5

PAPER_DARK, PAPER_LIGHT = (14, 13, 16), (232, 222, 196)
GRAY_DARK, GRAY_LIGHT = (0, 0, 0), (255, 255, 255)


# ----------------------------------------------------------------------------
# Utilidades de dibujo (todo sobre arrays numpy)
# ----------------------------------------------------------------------------
def smooth(x, a=0.0, b=1.0):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def vnoise(cells_x, seed):
    """Ruido de valor suave (bilineal) a 'cells_x' celdas de ancho."""
    r = np.random.default_rng(seed)
    cells_y = int(cells_x * H / W) + 1
    g = r.random((cells_y + 2, cells_x + 2))
    x, y = U * cells_x, V * cells_y
    x0, y0 = x.astype(int), y.astype(int)
    fx, fy = x - x0, y - y0
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    return (g[y0, x0] * (1 - fx) * (1 - fy) + g[y0, x0 + 1] * fx * (1 - fy) +
            g[y0 + 1, x0] * (1 - fx) * fy + g[y0 + 1, x0 + 1] * fx * fy)


def ell(cx, cy, rx, ry, rot=0.0):
    """Distancia normalizada a una elipse (<1 dentro)."""
    c, s = np.cos(rot), np.sin(rot)
    dx, dy = U - cx, V - cy
    x, y = (dx * c + dy * s) / rx, (-dx * s + dy * c) / ry
    return np.sqrt(x * x + y * y)


def ell_local(cx, cy, rx, ry, rot=0.0):
    """Igual que ell pero devuelve también las coordenadas locales (lx, ly)."""
    c, s = np.cos(rot), np.sin(rot)
    dx, dy = U - cx, V - cy
    lx, ly = (dx * c + dy * s) / rx, (-dx * s + dy * c) / ry
    return lx, ly, np.sqrt(lx * lx + ly * ly)


def stroke(pts, w0, w1=None, soft=0.005, n=18):
    """Trazo de grosor variable a lo largo de una curva Bézier (2-4 puntos).
    Devuelve una máscara 0..1."""
    w1 = w0 if w1 is None else w1
    P = np.array(pts, float)
    P[:, 0] *= A
    k = len(P) - 1
    t = np.linspace(0, 1, n + 1)
    curve = sum(comb(k, i) * ((1 - t) ** (k - i) * t ** i)[:, None] * P[i]
                for i in range(k + 1))
    m = np.zeros((H, W), np.float32)
    for i in range(n):
        a, b = curve[i], curve[i + 1]
        ab = b - a
        l2 = max(ab @ ab, 1e-9)
        tp = np.clip(((X - a[0]) * ab[0] + (V - a[1]) * ab[1]) / l2, 0, 1)
        d = np.hypot(X - (a[0] + tp * ab[0]), V - (a[1] + tp * ab[1]))
        w = 0.5 * (w0 + (w1 - w0) * ((i + tp) / n))
        m = np.maximum(m, np.clip((w - d) / soft + 0.5, 0, 1))
    return m


# ----------------------------------------------------------------------------
# Construcción del dibujo: devuelve un mapa de tonos 0 (carbón) .. 1 (papel)
# ----------------------------------------------------------------------------
def build_tone(seed=7, grain_amount=1.0):
    rng = np.random.default_rng(seed)
    tone = np.full((H, W), 0.10, np.float32)

    def ink(mask, val, k=1.0):
        nonlocal tone
        m = np.clip(mask * k, 0, 1)
        tone = tone * (1 - m) + val * m

    def line(pts, w0, val=0.05, w1=None, k=1.0):
        ink(stroke(pts, w0, w1), val, k)

    g1, g2, g3 = vnoise(10, seed + 1), vnoise(28, seed + 2), vnoise(70, seed + 3)

    # ---- fondo: sombra a los lados, algo de papel visible abajo-izquierda ----
    tone[:] = 0.07 + 0.10 * g1
    ink(smooth(1 - ell(0.02, 0.85, 0.10, 0.25)), 0.55, 0.0)

    # ---- cara: elipse grande, sombreada hacia los bordes ----
    r = ell(0.52, 0.53, 0.46, 0.50)
    face_mask = smooth(1 - r, 0.0, 0.05)
    base = 0.80 - 0.46 * r ** 2.2 + 0.10 * (g1 - 0.5)
    # luz desde arriba-izquierda
    base += 0.10 * (0.5 - U) * 0.6 + 0.08 * (0.45 - V)
    ink(face_mask, base)

    # ---- pelo: masa oscura arriba y a los lados ----
    hairline = 0.045 + 0.27 * (np.abs(U - 0.52) / 0.5) ** 1.7 + 0.04 * (g2 - 0.5)
    hair = smooth(hairline - V, -0.01, 0.02)
    hair_val = 0.06 + 0.32 * np.exp(-((U - 0.56) / 0.14) ** 2) * (V < 0.14)
    ink(hair, hair_val)
    # mechas (trazos de pelo, claros y oscuros)
    for _ in range(90):
        u0 = rng.uniform(0.05, 0.97)
        v0 = rng.uniform(0.0, 0.2 + 0.25 * abs(u0 - 0.5) * 2)
        dirx = (u0 - 0.52) * 0.35
        p = [(u0, v0), (u0 + dirx * 0.5 + rng.normal(0, .01), v0 + 0.05),
             (u0 + dirx + rng.normal(0, .01), v0 + 0.10 + rng.uniform(0, .05))]
        m = stroke(p, 0.004, 0.002, n=6) * hair
        ink(m, rng.choice([0.28, 0.02]), 0.7)
    # rizos del centro (garabatos en la coronilla)
    for cx, cy, rr in [(0.48, 0.07, 0.035), (0.60, 0.06, 0.04), (0.55, 0.11, 0.03), (0.68, 0.10, 0.03)]:
        a = rng.uniform(0, 6.28)
        pts = [(cx + rr * np.cos(a + k * 2.1), cy + rr * 0.8 * np.sin(a + k * 2.1)) for k in range(4)]
        line(pts, 0.006, 0.04, 0.003, k=0.9)

    # ---- orejas ----
    for cx, cy, flip in [(0.075, 0.47, 1), (0.935, 0.40, -1)]:
        e = ell(cx, cy, 0.065, 0.105, rot=0.15 * flip)
        ink(smooth(1 - e, 0, 0.1), 0.78 - 0.3 * e ** 2)
        line([(cx - 0.02 * flip, cy - 0.07), (cx + 0.02 * flip, cy - 0.01), (cx - 0.01 * flip, cy + 0.07)],
             0.010, 0.08)
        line([(cx + 0.03 * flip, cy - 0.05), (cx + 0.01 * flip, cy + 0.02)], 0.007, 0.10)
    ink(smooth(1 - ell(0.075, 0.545, 0.016, 0.014), 0, 0.5), 0.03)      # agujero del arete
    ink(smooth(1 - ell(0.07, 0.36, 0.05, 0.04), 0, 0.5), 0.08, 0.5)    # sombra tras oreja

    # ---- arrugas de la frente ----
    for y0, yc, x0, x1, w in [(0.215, 0.185, 0.24, 0.80, 0.007), (0.255, 0.23, 0.22, 0.82, 0.006)]:
        line([(x0, y0 + 0.01), (0.42, yc), (0.62, yc + 0.005), (x1, y0)], w, 0.20, k=0.8)
    line([(0.35, 0.14), (0.44, 0.19), (0.50, 0.22)], 0.006, 0.18, k=0.8)

    # ---- cejas arqueadas, parcialmente ocultas por las gafas ----
    line([(0.19, 0.255), (0.29, 0.205), (0.40, 0.20), (0.49, 0.245)],
         0.016, 0.04, 0.010)
    line([(0.57, 0.245), (0.66, 0.20), (0.78, 0.205), (0.85, 0.255)],
         0.016, 0.04, 0.010)
    for _ in range(10):
        u0 = rng.uniform(0.24, 0.46)
        line([(u0, 0.21 + rng.uniform(0, .04)),
              (u0 + 0.025, 0.19 + rng.uniform(0, .03))], 0.0025, 0.06, 0.0015)
    for _ in range(10):
        u0 = rng.uniform(0.62, 0.82)
        line([(u0, 0.20 + rng.uniform(0, .04)),
              (u0 + 0.025, 0.19 + rng.uniform(0, .03))], 0.0025, 0.06, 0.0015)

    # ---- cuencas y ojos ----
    eyes = [(0.335, 0.385, 0.135, 0.095, -0.08), (0.685, 0.365, 0.135, 0.095, -0.12)]
    for cx, cy, rx, ry, rot in eyes:
        # sombra de la cuenca
        socket = smooth(1 - ell(cx, cy - 0.01, rx * 1.55, ry * 1.8, rot), 0, 0.8)
        ink(socket, tone * 0.55, 0.9)

    for i, (cx, cy, rx, ry, rot) in enumerate(eyes):
        lx, ly, d = ell_local(cx, cy, rx, ry, rot)
        white = smooth(1 - d, 0.0, 0.08)
        # blanco con sombra del párpado superior y esquinas
        w_val = 0.97 - 0.50 * smooth(-ly, 0.0, 1.0) - 0.25 * d ** 3
        ink(white, w_val)
        # pupila grande mirando al frente, ligeramente arriba
        pcx = cx + (0.0 if i == 0 else 0.0)
        pcy = cy - 0.020
        pd = ell(pcx, pcy, 0.062, 0.070)
        iris = smooth(1 - pd, 0, 0.15) * white
        ink(iris, 0.05 + 0.25 * pd ** 2, 1.0)
        ink(smooth(1 - ell(pcx - 0.018, pcy - 0.022, 0.014, 0.014), 0, 0.5) * iris, 0.78, 0.9)  # brillo
        # contorno del párpado superior (grueso) y pliegues
        top = [(cx - rx * 1.02, cy - 0.010), (cx - rx * 0.4, cy - ry * 1.25),
               (cx + rx * 0.5, cy - ry * 1.25), (cx + rx * 1.02, cy - 0.005)]
        line(top, 0.022, 0.03, 0.022)
        top2 = [(x, y - 0.035) for x, y in top]
        line(top2, 0.013, 0.07, 0.007, k=0.85)
        top3 = [(x, y - 0.065) for x, y in top]
        line(top3, 0.010, 0.13, 0.005, k=0.7)
        # párpado inferior + bolsa
        bot = [(cx - rx * 0.95, cy + 0.015), (cx - rx * 0.3, cy + ry * 1.12),
               (cx + rx * 0.5, cy + ry * 1.12), (cx + rx * 1.0, cy + 0.01)]
        line(bot, 0.013, 0.05, 0.009)
        line([(x, y + 0.028) for x, y in bot], 0.011, 0.12, 0.006, k=0.8)
        line([(x, y + 0.052) for x, y in bot], 0.009, 0.16, 0.005, k=0.6)
        # contorno del globo ocular
        ink(smooth(1 - np.abs(ell(cx, cy, rx, ry, rot) - 1.0), 0.80, 1.0), 0.05, 0.9)

    # ---- gafas redondas, rasgo principal del retrato de referencia ----
    for cx, cy in [(0.335, 0.385), (0.685, 0.365)]:
        marco = ell(cx, cy, 0.165, 0.135, rot=-0.04)
        ink(smooth(1 - np.abs(marco - 1.0), 0.94, 1.0), 0.025, 1.0)
        marco_interior = ell(cx, cy, 0.154, 0.124, rot=-0.04)
        ink(smooth(1 - np.abs(marco_interior - 1.0), 0.94, 1.0), 0.09, 0.65)
    line([(0.49, 0.365), (0.525, 0.35), (0.55, 0.36)], 0.012, 0.025)
    line([(0.17, 0.36), (0.135, 0.34), (0.105, 0.35)], 0.009, 0.04, 0.005)
    line([(0.85, 0.34), (0.89, 0.32), (0.92, 0.34)], 0.009, 0.04, 0.005)

    # patas de gallo / arrugas laterales
    line([(0.185, 0.36), (0.14, 0.40)], 0.005, 0.1)
    line([(0.19, 0.40), (0.14, 0.44)], 0.005, 0.1)
    line([(0.835, 0.34), (0.885, 0.37)], 0.005, 0.1)
    line([(0.835, 0.385), (0.89, 0.42)], 0.005, 0.1)

    # ---- entrecejo y puente de la nariz ----
    ink(smooth(1 - ell(0.525, 0.31, 0.065, 0.05), 0, 0.9), 0.02)
    line([(0.50, 0.33), (0.45, 0.43), (0.43, 0.55)], 0.034, 0.03, 0.050)    # sombra izq. nariz
    line([(0.55, 0.33), (0.59, 0.43), (0.60, 0.55)], 0.034, 0.03, 0.046)    # sombra der. nariz
    ink(smooth(1 - ell(0.525, 0.45, 0.028, 0.12), 0, 1.0), 0.80, 0.6)       # lomo claro
    line([(0.47, 0.30), (0.34, 0.30)], 0.022, 0.03, 0.010)
    line([(0.57, 0.30), (0.72, 0.28)], 0.022, 0.03, 0.010)

    # ---- mejillas y arrugas de expresión ----
    for pts, w, v in [
        ([(0.21, 0.575), (0.25, 0.625), (0.30, 0.655)], 0.011, 0.08),
        ([(0.25, 0.545), (0.285, 0.58), (0.325, 0.605)], 0.008, 0.12),
        ([(0.16, 0.60), (0.20, 0.65)], 0.006, 0.18),
        ([(0.74, 0.585), (0.83, 0.545), (0.90, 0.60)], 0.016, 0.05),
        ([(0.80, 0.50), (0.88, 0.50), (0.93, 0.52)], 0.006, 0.12),
        ([(0.70, 0.58), (0.76, 0.52)], 0.006, 0.15),
    ]:
        line(pts, w, v)

    # ---- boca: sonrisa enorme con dientes ----
    rot = -0.20
    lx, ly, d = ell_local(0.545, 0.725, 0.272, 0.115, rot)
    mouth = smooth(1 - d, 0.0, 0.05)
    ink(mouth, 0.06)
    teeth_zone = smooth(0.90 - d, 0.0, 0.06)
    tooth_val = 0.93 - 0.30 * d ** 2
    ink(teeth_zone, tooth_val)
    sep = 0.05 + 0.55 * lx ** 2 - 0.25                 # línea entre fila superior e inferior (sonrisa)
    ink(smooth(1 - np.abs(ly - sep) / 0.06, 0, 1) * teeth_zone, 0.07, 1.0)
    # separaciones verticales de los dientes (fila superior / inferior desfasadas)
    for gx in [-0.80, -0.55, -0.31, -0.07, 0.17, 0.42, 0.66, 0.86]:
        up = smooth(1 - np.abs(lx - gx - 0.03 * ly) / 0.035, 0, 1) * (ly < sep)
        ink(up * teeth_zone, 0.10, 0.95)
    for gx in [-0.70, -0.42, -0.14, 0.12, 0.38, 0.62]:
        lo = smooth(1 - np.abs(lx - gx) / 0.035, 0, 1) * (ly > sep)
        ink(lo * teeth_zone, 0.12, 0.85)
    # contorno de los labios
    ink(smooth(1 - np.abs(d - 0.98), 0.90, 1.0), 0.03, 1.0)
    line([(0.26, 0.755), (0.33, 0.835), (0.50, 0.872), (0.68, 0.815)], 0.018, 0.06, 0.030)  # labio inferior
    line([(0.38, 0.905), (0.50, 0.92), (0.62, 0.90)], 0.012, 0.15, k=0.8)
    line([(0.68, 0.815), (0.78, 0.76), (0.84, 0.66)], 0.016, 0.08)
    # comisura izquierda
    ink(smooth(1 - ell(0.275, 0.71, 0.02, 0.025), 0, 1.0), 0.03, 0.9)

    # ---- nariz bulbosa (se dibuja sobre la boca) ----
    nose = ell(0.525, 0.628, 0.100, 0.085)
    ink(smooth(1 - nose, 0, 0.10), 0.97 - 0.32 * nose ** 3)
    ink(smooth(1 - np.abs(nose - 1.0), 0.80, 1.0) * ((U < 0.545) | (V > 0.66)), 0.05, 0.95)
    line([(0.445, 0.595), (0.447, 0.66), (0.50, 0.705)], 0.016, 0.04, 0.010)
    line([(0.50, 0.705), (0.555, 0.712), (0.60, 0.68)], 0.016, 0.04, 0.010)
    line([(0.60, 0.60), (0.612, 0.66)], 0.010, 0.10)
    line([(0.49, 0.665), (0.515, 0.675)], 0.010, 0.10)
    ink(smooth(1 - ell(0.53, 0.72, 0.09, 0.022), 0, 1.0), 0.04, 0.5)

    # ---- sombras de la mandíbula ----
    ink(smooth(1 - ell(0.10, 0.80, 0.14, 0.18), 0, 1.0), 0.04, 0.8)
    ink(smooth(1 - ell(0.93, 0.70, 0.08, 0.14), 0, 1.0), 0.05, 0.7)

    # ---- textura de carboncillo: grano + trazos diagonales en sombras ----
    grain = ((g3 - 0.5) * 0.30 + (rng.random((H, W)) - 0.5) * 0.12)
    grain *= grain_amount
    tone += grain * (0.25 + 0.75 * (1 - np.abs(tone - 0.5) * 1.2))
    ang = 0.9
    hatch_coord = (X * np.cos(ang) + V * np.sin(ang)) * 85 + vnoise(14, seed + 9) * 3.2
    hatch = (np.mod(hatch_coord, 1.0) < 0.38).astype(np.float32)
    shade = smooth(0.62 - tone, 0.0, 0.5)
    tone -= 0.16 * grain_amount * hatch * shade
    return np.clip(tone, 0, 1)


# ----------------------------------------------------------------------------
# Cuantización y paleta
# ----------------------------------------------------------------------------
def to_rgb(tone, levels=6, dither=True, paper=True, contrast=1.25):
    g = np.clip((tone - 0.5) * contrast + 0.5, 0, 1)
    if dither:
        t = np.tile(BAYER4, (H // 4 + 1, W // 4 + 1))[:H, :W]
        g = g + t / max(levels - 1, 1)
    idx = np.clip(np.round(g * (levels - 1)), 0, levels - 1).astype(int)
    dark, light = (PAPER_DARK, PAPER_LIGHT) if paper else (GRAY_DARK, GRAY_LIGHT)
    pal = np.array([[dark[c] + (light[c] - dark[c]) * i / max(levels - 1, 1) for c in range(3)]
                    for i in range(levels)]).round().astype(np.uint8)
    return pal[idx]                                  # (H, W, 3)


class CarboncilloAnimado:
    """Alterna cuatro acabados del retrato en un ciclo visual de 2,5 segundos."""

    DURACION_CICLO = 0.9
    DURACION_ESTADO = DURACION_CICLO / 4
    DURACION_TRANSICION = 0.10

    def __init__(self):
        configuraciones = (
            (3, 7, False, 0.25),
            (6, 19, True, 0.90),
            (10, 31, False, 0.45),
            (16, 43, True, 1.00),
        )
        self.fotogramas = []
        for niveles, semilla, dithering, cantidad_grano in configuraciones:
            tonos = build_tone(semilla, cantidad_grano)
            rgb = to_rgb(tonos, niveles, dithering)
            fotograma = pygame.Surface((W, H))
            pygame.surfarray.blit_array(fotograma, np.transpose(rgb, (1, 0, 2)))
            self.fotogramas.append(fotograma)
        self.compuesto = pygame.Surface((W, H))

    def dibujar(self, destino, tiempo):
        fase = (tiempo % self.DURACION_CICLO) / self.DURACION_ESTADO
        indice = int(fase)
        progreso = fase - indice
        actual = self.fotogramas[indice]
        siguiente = self.fotogramas[(indice + 1) % len(self.fotogramas)]

        self.compuesto.blit(actual, (0, 0))
        inicio_transicion = 1.0 - self.DURACION_TRANSICION / self.DURACION_ESTADO
        if progreso >= inicio_transicion:
            alpha = int(
                255 * (progreso - inicio_transicion) / (1.0 - inicio_transicion)
            )
            siguiente.set_alpha(alpha)
            self.compuesto.blit(siguiente, (0, 0))
            siguiente.set_alpha(None)

        imagen = pygame.transform.scale(self.compuesto, destino.get_size())
        destino.blit(imagen, (0, 0))


def play_wake_animation(
    screen,
    clock=None,
    exit_text="EXIT",
    exit_delay=5.0,
    button_renderer=None,
):
    """Muestra el ciclo de carboncillo hasta que el jugador salga."""
    clock = clock or pygame.time.Clock()
    animacion = CarboncilloAnimado()
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
        boton = None
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
            escala = min(ancho / (W * SCALE), alto / (H * SCALE))
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


# ----------------------------------------------------------------------------
# Ventana pygame
# ----------------------------------------------------------------------------
def main():
    pygame.init()
    screen = pygame.display.set_mode((W * SCALE, H * SCALE))
    pygame.display.set_caption("Carboncillo procedural - pixel art")
    font = pygame.font.SysFont("consolas", 14)
    clock = pygame.time.Clock()

    animacion = CarboncilloAnimado()
    inicio = pygame.time.get_ticks()

    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                pygame.quit()
                return
            if e.type == pygame.KEYDOWN and e.key == pygame.K_s:
                pygame.image.save(
                    animacion.fotogramas[0], "carboncillo_pequeno.png"
                )
                pygame.image.save(
                    pygame.transform.scale(
                        animacion.fotogramas[0], (W * 10, H * 10)
                    ),
                    "carboncillo_grande.png",
                )

        tiempo = (pygame.time.get_ticks() - inicio) / 1000.0
        animacion.dibujar(screen, tiempo)
        screen.blit(font.render("S: guardar   ESC: salir", True, (255, 255, 0)), (4, 4))
        pygame.display.flip()
        clock.tick(30)


if __name__ == "__main__":
    main()