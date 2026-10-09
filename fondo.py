import math
import random

import pygame

from plataformas import color_desde_hue


# Caché de superficies reutilizadas entre frames para el fondo segmentado.
_CACHE_FONDO = {}


def _obtener_superficie(clave, tam):
    """Devuelve una Surface SRCALPHA reutilizada del tamaño pedido."""
    capa = _CACHE_FONDO.get(clave)
    if capa is None or capa.get_size() != tam:
        capa = pygame.Surface(tam, pygame.SRCALPHA)
        _CACHE_FONDO[clave] = capa
    else:
        capa.fill((0, 0, 0, 0))
    return capa


# ---------------------------------------------------------------------------
# Trazo orgánico: contornos ondulados que imitan una pincelada caricaturesca
# en vez de círculos/elipses perfectos. Es la base "psicodélica" del fondo.
# ---------------------------------------------------------------------------

def _punto_organico(centro, radio, angulo, tiempo, fase, amplitud=0.42, asimetria=0.0):
    """Deforma un radio con varias ondas superpuestas, como un trazo a mano.

    `asimetria` rompe la simetría radial (más "dibujado a mano", menos
    geométrico) añadiendo un lóbulo dominante en una dirección, como una
    pincelada caricaturesca que nunca es perfectamente redonda.
    """
    ondulacion = (
        math.sin(angulo * 3 + fase) * amplitud
        + math.sin(angulo * 7 - fase * 1.7 + tiempo * 1.3) * amplitud * 0.45
        + math.sin(angulo * 1.5 + tiempo * 0.6 + fase) * amplitud * 0.55
        + math.sin(angulo * 2 + fase * 0.6) * asimetria
    )
    r = radio * max(0.22, 1 + ondulacion)
    return (
        centro[0] + math.cos(angulo) * r,
        centro[1] + math.sin(angulo) * r,
    )


def _mancha_organica(capa, centro, radio, color, alpha, tiempo, fase, puntos=26, asimetria=0.12):
    """Mancha con contorno ondulado: la unidad básica de 'pincelada' del fondo."""
    pts = [
        _punto_organico(centro, radio, (i / puntos) * math.tau, tiempo, fase, asimetria=asimetria)
        for i in range(puntos)
    ]
    pygame.draw.polygon(capa, (*color, alpha), pts)


def _trazo_contorno(capa, centro, radio, color, alpha, tiempo, fase, grosor=3):
    """Línea de contorno tipo tinta, exagerando el borde de la mancha (caricatura)."""
    pts = [
        _punto_organico(centro, radio * 1.05, (i / 30) * math.tau, tiempo, fase, 0.5, asimetria=0.15)
        for i in range(30)
    ]
    pygame.draw.polygon(capa, (*color, alpha), pts, grosor)


def _trazo_tinta(capa, centro, radio, tiempo, fase, alpha=150, grosor=4):
    """Contorno oscuro tipo 'tinta de cómic': el rasgo caricaturesco más
    reconocible (bordes gruesos casi negros alrededor de formas de color)."""
    pts = [
        _punto_organico(centro, radio * 1.08, (i / 34) * math.tau, tiempo, fase, 0.48, asimetria=0.14)
        for i in range(34)
    ]
    pygame.draw.polygon(capa, (18, 14, 28, alpha), pts, grosor)


def _puntos_halftone(superficie, ancho, alto, tiempo, hue_base, paso=52, alpha=26):
    """Textura de puntos estilo cómic/pop-art (halftone), muy sutil, para que
    el fondo se lea como una lámina impresa en vez de un degradado liso.

    Rendimiento: el paso de la grilla se subió de 34 a 52px (menos de la
    mitad de puntos) y el color solo se recalcula cada pocas columnas en
    vez de en cada punto individual: la conversión HSV->RGB (``color_desde_hue``)
    es lo más caro de este bucle y el matiz apenas cambia entre puntos
    vecinos, así que reutilizarlo es imperceptible mientras ahorra muchas
    llamadas por fotograma.
    """
    capa = _obtener_superficie("halftone", (ancho, alto))
    fila = 0
    for y in range(-paso, alto + paso, paso):
        desfase = (paso // 2) if fila % 2 else 0
        color = None
        for indice_col, x in enumerate(range(-paso, ancho + paso, paso)):
            cx = x + desfase
            cy = y
            onda = math.sin(cx * 0.01 + tiempo * 0.4) + math.cos(cy * 0.013 - tiempo * 0.3)
            radio_punto = max(1.5, 3.2 + onda * 1.6)
            if color is None or indice_col % 3 == 0:
                hue = (hue_base + (cx / ancho) * 0.15 + tiempo * 0.02) % 1.0
                color = color_desde_hue(hue, 0.4, 0.4)
            pygame.draw.circle(capa, (*color, alpha), (cx, cy), int(radio_punto))
        fila += 1
    superficie.blit(capa, (0, 0))


def _fondo_degradado(superficie, ancho, alto, hue_base, tiempo):
    """Cielo de fondo en degradado vertical (en vez de un color plano) para
    dar más profundidad atmosférica al estilo pop/abstracto."""
    color_arriba = color_desde_hue((hue_base - 0.04) % 1.0, 0.4, 0.97)
    color_abajo = color_desde_hue((hue_base + 0.05) % 1.0, 0.3, 0.8)
    franjas = 48
    alto_franja = math.ceil(alto / franjas) + 1
    for i in range(franjas):
        t = i / (franjas - 1)
        color = [
            int(color_arriba[c] + (color_abajo[c] - color_arriba[c]) * t)
            for c in range(3)
        ]
        pygame.draw.rect(superficie, color, (0, int(t * alto), ancho, alto_franja))


def _dibujar_capas_parallax(superficie, ancho, alto, hue_base, tiempo):
    capas = (
        (0.025, 0.12, 0.20, 0.10),
        (0.055, 0.22, 0.30, 0.14),
        (0.10, 0.34, 0.42, 0.18),
    )
    for indice, (velocidad, radio_base, saturacion, valor) in enumerate(capas):
        capa = _obtener_superficie(("parallax", indice), (ancho, alto))
        tono = (hue_base + indice * 0.19 + 0.5) % 1.0
        color = color_desde_hue(tono, saturacion, valor)
        acento = color_desde_hue(
            (tono + 0.12) % 1.0, saturacion, min(1.0, valor + 0.12)
        )
        for forma in range(4):
            radio = int(ancho * radio_base * (0.72 + (forma % 3) * 0.22))
            paso = ancho + radio * 2
            x = int(
                (forma * ancho / 2 - tiempo * ancho * velocidad) % paso
                - radio
            )
            y = int(alto * (0.18 + (forma * 0.29 + indice * 0.17) % 0.68))
            for centro_x in (x - paso, x, x + paso):
                centro = (centro_x, y)
                puntos = [
                    _punto_organico(
                        centro,
                        radio,
                        angulo,
                        tiempo * (0.25 + velocidad),
                        indice * 2.4 + forma,
                        amplitud=0.26,
                        asimetria=0.12,
                    )
                    for angulo in (i * math.tau / 18 for i in range(18))
                ]
                pygame.draw.polygon(
                    capa,
                    (*color, 255),
                    [(int(px), int(py)) for px, py in puntos],
                )
                pygame.draw.ellipse(
                    capa,
                    (*acento, 180),
                    (
                        centro_x - radio // 3,
                        y - radio // 2,
                        radio,
                        max(6, radio // 4),
                    ),
                )
        capa.set_alpha(int(62 + indice * 17))
        superficie.blit(capa, (0, 0))


class ParticulaAbstracta:
    """Mancha de color translúcida, con contorno orgánico, que flota por el fondo."""

    def __init__(self, ancho, alto):
        self.ancho = ancho
        self.alto = alto
        self.pos = pygame.Vector2(random.uniform(0, ancho), random.uniform(0, alto))
        self.radio = random.uniform(34, 105)
        self.hue = random.random()
        self.vel = pygame.Vector2(random.uniform(-0.25, 0.25), random.uniform(-0.15, 0.15))
        self.fase = random.uniform(0, math.tau)
        self.fase2 = random.uniform(0, math.tau)
        self.secciones = random.randint(8, 15)
        self.giro = random.uniform(0.7, 1.6)

        # Rendimiento: dibujar esta mancha implica crear una Surface nueva
        # y trazar varios polígonos orgánicos con muchos puntos; hacerlo en
        # cada fotograma para las 12 partículas es caro. La forma se
        # recalcula solo cada pocos fotogramas (la animación es lenta, así
        # que no se nota) y mientras tanto se reutiliza la última capa,
        # reposicionada según el movimiento real de la partícula.
        self._capa_cache = None
        self._centro_cache = None
        self._contador_regen = random.randint(0, 4)  # desfasado entre partículas

    def actualizar(self, dt=1 / 60):
        factor_fotograma = dt * 60
        self.pos.x = (self.pos.x + self.vel.x * factor_fotograma) % self.ancho
        self.pos.y = (self.pos.y + self.vel.y * factor_fotograma) % self.alto

    def dibujar(self, superficie, tiempo):
        self._contador_regen += 1
        if self._capa_cache is not None and self._contador_regen % 4 != 0:
            superficie.blit(self._capa_cache, self.pos - self._centro_cache)
            return

        hue_base = (self.hue + tiempo * 0.02) % 1.0
        radio = self.radio + math.sin(tiempo * 2 + self.fase) * 8
        capa = pygame.Surface((radio * 2.6, radio * 2.6), pygame.SRCALPHA)
        centro = (radio * 1.3, radio * 1.3)

        # Mancha principal con borde ondulado (pincelada caricaturesca).
        color_principal = color_desde_hue(hue_base, 0.7, 0.95)
        _mancha_organica(capa, centro, radio, color_principal, 82, tiempo, self.fase, asimetria=0.16)
        _trazo_contorno(capa, centro, radio, color_desde_hue(hue_base, 0.85, 0.55), 100, tiempo, self.fase, grosor=3)
        # Contorno de tinta oscura: el "outline" de cómic que hace que la
        # mancha se lea como un personaje/objeto dibujado, no como una mancha borrosa.
        _trazo_tinta(capa, centro, radio, tiempo, self.fase, alpha=130, grosor=4)

        # Salpicaduras de color complementario para el efecto psicodélico "pop".
        hue_complementario = (hue_base + 0.5) % 1.0
        for i in range(self.secciones):
            angulo = self.fase2 + i * (math.tau / self.secciones) + tiempo * self.giro
            distancia = 5 + i * (radio / self.secciones) * 0.75
            offset = pygame.Vector2(math.cos(angulo), math.sin(angulo)) * distancia
            usa_complementario = i % 3 == 0
            hue_punto = hue_complementario if usa_complementario else (hue_base + i / self.secciones * 0.28) % 1.0
            color = color_desde_hue(hue_punto, 0.8, 0.95)
            radio_punto = max(3, int((radio * 0.2) - i * 0.35))
            centro_punto = (centro[0] + offset.x, centro[1] + offset.y)
            _mancha_organica(
                capa, centro_punto, radio_punto, color, 200, tiempo * 1.4, self.fase + i, puntos=10
            )

        base = color_desde_hue(hue_base, 0.5, 0.85)
        pygame.draw.circle(capa, (*base, 35), centro, int(radio * 0.85), 2)

        # Brillo tipo "cel-shading" de caricatura: un óvalo blanco desplazado
        # que simula luz reflejada, típico del cartoon plano.
        brillo_pos = (
            centro[0] - radio * 0.32,
            centro[1] - radio * 0.38 + math.sin(tiempo * 1.5 + self.fase) * 3,
        )
        brillo = pygame.Surface((int(radio * 0.7), int(radio * 0.42)), pygame.SRCALPHA)
        pygame.draw.ellipse(brillo, (255, 255, 255, 60), brillo.get_rect())
        brillo_rot = pygame.transform.rotate(brillo, math.degrees(self.fase) % 40 - 20)
        capa.blit(brillo_rot, brillo_rot.get_rect(center=brillo_pos))

        self._capa_cache = capa
        self._centro_cache = pygame.Vector2(centro)
        superficie.blit(capa, self.pos - self._centro_cache)


_VUELTAS_REMOLINO = 2.8
_HILOS_REMOLINO = 4


def _dibujar_remolino(superficie, x, y, radio, hue, tiempo, indice):
    """Espiral con grosor pulsante y goteo final, como una pincelada de acrílico.

    Rendimiento: esta era la función más costosa de todo el fondo. Con 4
    hilos y hasta 160 pasos por remolino, cada redibujado del fondo podía
    llegar a llamar ``color_desde_hue`` (conversión HSV->RGB) y
    ``pygame.draw.line`` más de 600 veces solo aquí, multiplicado por los
    3 remolinos del fondo. Se reduce el número de pasos y se recalcula el
    color cada varios segmentos en vez de en cada uno: el degradado de
    color a lo largo del brazo sigue viéndose suave porque el matiz
    cambia poco entre segmentos vecinos.
    """
    tam = (radio * 2, radio * 2)
    capa = _obtener_superficie(("remolino", indice), tam)
    centro = pygame.Vector2(radio, radio)
    pasos = min(70, max(30, int(radio * 0.45)))

    for hilo in range(_HILOS_REMOLINO):
        fase_hilo = hilo * (math.tau / _HILOS_REMOLINO)
        anterior = None
        color = None
        for paso in range(pasos + 1):
            t = paso / pasos
            angulo = (
                t * math.tau * _VUELTAS_REMOLINO
                + fase_hilo
                + tiempo * (1.3 + indice * 0.4)
                + math.sin(t * math.tau * 2 + tiempo) * 0.25  # deformación orgánica del brazo
            )
            distancia = 8 + t * (radio - 16) + math.sin(t * 14 + tiempo * 2) * (radio * 0.03)
            punto = (
                int(centro.x + math.cos(angulo) * distancia),
                int(centro.y + math.sin(angulo) * distancia),
            )
            if anterior is not None:
                if color is None or paso % 4 == 0:
                    color = color_desde_hue(
                        (hue + t * 0.4 + hilo / _HILOS_REMOLINO * 0.18 + tiempo * 0.05) % 1.0, 0.85, 1.0
                    )
                grosor = max(1, int(6 * (1 - t) + 2 * math.sin(tiempo * 3 + hilo)) + 1)
                pygame.draw.line(capa, (*color, 170), anterior, punto, grosor)
            anterior = punto

        # Gota de pintura al final del brazo, con leve caída animada.
        caida = abs(math.sin(tiempo * 0.8 + fase_hilo)) * radio * 0.12
        gota_pos = (anterior[0], anterior[1] + caida)
        color_gota = color_desde_hue((hue + 0.5 + hilo * 0.1) % 1.0, 0.9, 1.0)
        pygame.draw.circle(capa, (*color_gota, 150), (int(gota_pos[0]), int(gota_pos[1])), max(2, int(radio * 0.035)))

    color_nucleo = color_desde_hue(hue, 0.6, 1.0)
    pygame.draw.circle(capa, (*color_nucleo, 170), centro, max(5, int(radio * 0.07)))
    pygame.draw.circle(capa, (*color_desde_hue((hue + 0.5) % 1.0, 0.9, 1.0), 90), centro, max(9, int(radio * 0.12)), 2)
    superficie.blit(capa, (x, y))


def _dibujar_goteo(superficie, x, y, longitud, hue, tiempo, fase, grosor=6):
    """Chorro de pintura cayendo, con ancho decreciente y gota final."""
    avance = (math.sin(tiempo * 0.5 + fase) * 0.5 + 0.5)  # 0..1, oscila
    largo_actual = longitud * (0.3 + avance * 0.7)
    color = color_desde_hue(hue, 0.75, 0.9)
    tamano = (grosor * 4, int(longitud * 1.3) + 20)
    clave = ("goteo", grosor, int(longitud), tamano[0], tamano[1])
    capa = _obtener_superficie(clave, tamano)

    segmentos = 18
    for i in range(segmentos):
        t = i / segmentos
        if t * longitud > largo_actual:
            break
        alpha = int(150 * (1 - t * 0.6))
        ancho = max(1, int(grosor * (1 - t * 0.7)))
        py = int(t * longitud)
        pygame.draw.line(capa, (*color, alpha), (grosor * 2, py), (grosor * 2, py + 6), ancho)

    pygame.draw.circle(
        capa, (*color, 190), (grosor * 2, int(min(largo_actual, longitud))), max(3, grosor - 1)
    )
    superficie.blit(capa, (x - grosor * 2, y))


def _dibujar_caleidoscopio(superficie, centro, radio, hue_base, tiempo, ancho, alto, brazos=6):
    """Mandala giratorio de cuñas translúcidas: el 'motor' psicodélico del fondo."""
    capa = _obtener_superficie("caleidoscopio", (ancho, alto))
    cx, cy = centro
    rotacion = tiempo * 0.12

    for brazo in range(brazos):
        angulo_ini = rotacion + brazo * (math.tau / brazos)
        angulo_fin = angulo_ini + (math.tau / brazos) * 0.72
        hue = (hue_base + brazo / brazos * 0.6 + tiempo * 0.03) % 1.0
        color = color_desde_hue(hue, 0.7, 0.9)
        pulso = radio * (0.75 + math.sin(tiempo * 1.5 + brazo) * 0.2)

        puntos = [(cx, cy)]
        pasos_arco = 10
        for i in range(pasos_arco + 1):
            a = angulo_ini + (angulo_fin - angulo_ini) * (i / pasos_arco)
            puntos.append((cx + math.cos(a) * pulso, cy + math.sin(a) * pulso))
        pygame.draw.polygon(capa, (*color, 26), puntos)
        # Filo de cada cuña ligeramente marcado, como viñetas de cómic recortadas.
        pygame.draw.polygon(capa, (*color_desde_hue(hue, 0.9, 0.6), 22), puntos, 2)

    superficie.blit(capa, (0, 0))


# ---------------------------------------------------------------------------
# Lluvia de caras pensativas
# A medida que suben los niveles caen más caras, más grandes y más
# deformes/psicodélicas, hasta que el fondo entero se llena de ellas.
# ---------------------------------------------------------------------------

_TINTA = (18, 14, 28)          # tinta de cómic para los contornos
_TAMANOS_CARA = (24, 36, 52)   # radios base: lejos, medio, cerca
_ALPHA_CARA = (150, 205, 245)  # las lejanas son más translúcidas
_PESOS_TAM = (0.45, 0.35, 0.20)
_NUM_HUES_CARA = 6
_ANGULOS_CARA = (-12, -6, 0, 6, 12)  # inclinaciones pre-renderizadas (balanceo)
_ESCALA_ESTILO = (1.0, 1.1, 1.2)
_CARAS_MIN = 6
_CARAS_MAX = 68
_GOTAS_MAX = 170

_LLUVIA = {
    "dim": None,
    "estilo": -1,
    "etapa_distorsion": -1,
    "sprites": [],
    "caras": [],
    "gotas": [],
    "t": None,
}
_CACHE_VINETA = {}


def _c(hue, sat, val):
    """Color RGB (tupla de enteros) a partir de matiz/saturación/valor."""
    return tuple(int(v) for v in color_desde_hue(hue % 1.0, sat, val)[:3])


def _mezclar(a, b, t):
    """Interpolación lineal entre dos colores RGB."""
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _crear_cara(R, hue, estilo, rng, distorsion=0.0):
    """Dibuja una cara pensativa (ceja alzada, mirada arriba, mano en la
    barbilla y burbujas de pensamiento). Devuelve sus frames inclinados.

    estilo 0: cartoon sencillo.
    estilo 1: pupilas hipnóticas, lágrimas de pintura y aura.
    estilo 2: además se derrite por abajo y le sale un tercer ojo.
    `distorsion` aumenta los rasgos desiguales y ondulados entre niveles.
    """
    w, h = int(R * 3.0), int(R * 3.7)
    capa = pygame.Surface((w, h), pygame.SRCALPHA)
    cx, cy = w / 2, R * 1.9
    fase = rng.uniform(0, math.tau)
    g = max(2, R // 11)
    piel = _c(hue, 0.62, 0.98)
    pop = _c(hue + 0.5, 0.9, 1.0)

    def P(dx, dy):
        return (int(cx + dx * R), int(cy + dy * R))

    if estilo >= 1:  # aura psicodélica
        pygame.draw.circle(capa, (*pop, 90), P(0, 0), int(R * 1.16), max(2, R // 9))

    if estilo >= 2:  # chorreones de la cara derritiéndose
        goteos = [(dx, rng.uniform(0.35, 0.7)) for dx in (-0.62, -0.15, 0.62)]
        for grosor_g, color in ((int(R * 0.15) + 2 * g, _TINTA), (int(R * 0.15), piel)):
            for dx, largo in goteos:
                fin = P(dx, 0.95 + largo)
                pygame.draw.line(capa, color, P(dx, 0.7), fin, grosor_g)
                pygame.draw.circle(capa, color, fin, grosor_g // 2 + 1)

    # Cara con contorno orgánico y borde de tinta.
    pts = [
        _punto_organico((cx, cy), R, (i / 36) * math.tau, 0.0, fase,
                        amplitud=0.05 + 0.035 * estilo + 0.2 * distorsion,
                        asimetria=0.05 + 0.03 * estilo + 0.18 * distorsion)
        for i in range(36)
    ]
    pygame.draw.polygon(capa, (*piel, 255), pts)
    pygame.draw.polygon(capa, (*_TINTA, 255), pts, g)

    # Mejillas de color complementario.
    for dx in (-0.62, 0.66):
        pygame.draw.circle(capa, (*pop, 110), P(dx, 0.28), max(2, int(R * 0.2)))

    # Ojos asimétricos mirando hacia arriba.
    for indice, (dx, dy, rel) in enumerate(((-0.36, -0.10, 0.23), (0.38, -0.16, 0.29))):
        lado = -1 if indice == 0 else 1
        dx += lado * math.sin(fase + indice) * 0.14 * distorsion
        dy += math.cos(fase * 1.3 + indice) * 0.12 * distorsion
        ex, ey = P(dx, dy)
        er = max(3, int(rel * R * (1 + lado * 0.25 * distorsion)))
        pygame.draw.circle(capa, (255, 255, 255, 255), (ex, ey), er)
        pygame.draw.circle(capa, (*_TINTA, 255), (ex, ey), er, max(2, g - 1))
        px, py = ex + int(er * 0.22), ey - int(er * 0.28)
        pr = max(2, int(er * 0.5))
        if estilo == 0:
            pygame.draw.circle(capa, (*_TINTA, 255), (px, py), pr)
            pygame.draw.circle(capa, (255, 255, 255, 255), (px - pr // 3, py - pr // 3), max(1, pr // 3))
        else:  # anillos hipnóticos
            anillos = 3 if estilo == 1 else 4
            for j in range(anillos):
                col = pop if j % 2 == 0 else _TINTA
                pygame.draw.circle(capa, (*col, 255), (px, py), max(1, int(pr * (1 - j / anillos))))
        if estilo >= 1:  # lágrima de pintura
            pygame.draw.line(capa, (*pop, 220), (ex, ey + er), (ex, ey + er + int(R * 0.5)), max(2, g - 1))
            pygame.draw.circle(capa, (*pop, 220), (ex, ey + er + int(R * 0.5)), max(2, g))

    if estilo >= 2:  # tercer ojo
        ex, ey = P(0, -0.80)
        er = max(3, int(R * 0.11))
        pygame.draw.circle(capa, (255, 255, 255, 255), (ex, ey), er)
        pygame.draw.circle(capa, (*_TINTA, 255), (ex, ey), er, 2)
        pygame.draw.circle(capa, (*pop, 255), (ex, ey), max(1, er // 2))

    # Cejas: una alzada y otra más baja ("hmmm...").
    gc = max(2, R // 9)
    pygame.draw.line(capa, _TINTA, P(-0.62, -0.50), P(-0.12, -0.66), gc)
    pygame.draw.line(capa, _TINTA, P(0.10, -0.60), P(0.68, -0.54), gc)

    # Boquita torcida de duda.
    boca = [
        P(
            -0.05 + 0.45 * (u / 8),
            0.40 + (0.05 + 0.14 * distorsion) * math.sin(u / 8 * math.tau * 1.5 + fase),
        )
        for u in range(9)
    ]
    pygame.draw.lines(capa, _TINTA, False, boca, g)

    # Mano en la barbilla.
    mx, my = P(0.26, 0.95)
    mr = int(R * 0.32)
    pygame.draw.circle(capa, (*_mezclar(piel, _TINTA, 0.10), 255), (mx, my), mr)
    pygame.draw.circle(capa, (*_TINTA, 255), (mx, my), mr, max(2, g - 1))
    for dx in (-0.12, 0.0, 0.12):
        pygame.draw.line(capa, _TINTA, (mx + int(dx * R), my - int(R * 0.30)),
                         (mx + int(dx * R), my - int(R * 0.08)), 2)

    # Burbujas de pensamiento.
    for dx, dy, rel in ((0.95, -1.05, 0.09), (1.15, -1.32, 0.13)):
        bx, by = P(dx, dy)
        br = max(2, int(rel * R))
        pygame.draw.circle(capa, (255, 255, 255, 235), (bx, by), br)
        pygame.draw.circle(capa, (*_TINTA, 255), (bx, by), br, 2)

    return [pygame.transform.rotozoom(capa, a, 1.0) for a in _ANGULOS_CARA]


def _construir_sprites(estilo, distorsion=0.0):
    """Pool de caras (3 tamaños x varios matices) para una etapa de distorsión.
    Se genera una sola vez por etapa; el alpha de profundidad queda 'horneado'."""
    etapa_distorsion = round(distorsion * 9)
    rng = random.Random(1234 + estilo * 10 + etapa_distorsion)
    sprites = []
    for tam, radio in enumerate(_TAMANOS_CARA):
        for k in range(_NUM_HUES_CARA):
            hue = (k / _NUM_HUES_CARA + rng.uniform(-0.03, 0.03)) % 1.0
            frames = _crear_cara(
                int(radio * _ESCALA_ESTILO[estilo]), hue, estilo, rng, distorsion
            )
            for f in frames:
                f.fill((255, 255, 255, _ALPHA_CARA[tam]), special_flags=pygame.BLEND_RGBA_MULT)
            sprites.append((tam, frames))
    return sprites


def _nueva_cara(ancho, alto, desde_arriba):
    tam = random.choices(range(3), weights=_PESOS_TAM)[0]
    radio = _TAMANOS_CARA[tam]
    y = random.uniform(-alto * 0.6, -radio * 3) if desde_arriba else random.uniform(-radio * 3, alto)
    return {
        "x": random.uniform(0, ancho),
        "y": y,
        "vy": (70 + radio * 3.2) * random.uniform(0.85, 1.15),
        "fase": random.uniform(0, math.tau),
        "sprite": tam * _NUM_HUES_CARA + random.randrange(_NUM_HUES_CARA),
        "tam": tam,
    }


def _crear_gotas(ancho, alto):
    """Hilos finos de lluvia de colores que acompañan a las caras."""
    return [
        (random.uniform(0, ancho), random.uniform(0, alto), random.uniform(260, 520),
         random.randint(14, 34), random.randrange(12))
        for _ in range(_GOTAS_MAX)
    ]


def _obtener_vineta(ancho, alto):
    """Viñeta morada oscura (se cachea; se escala una imagen diminuta)."""
    v = _CACHE_VINETA.get((ancho, alto))
    if v is None:
        pw, ph = 48, 27
        pequena = pygame.Surface((pw, ph), pygame.SRCALPHA)
        for yy in range(ph):
            for xx in range(pw):
                d = math.hypot((xx / (pw - 1) - 0.5) * 2, (yy / (ph - 1) - 0.5) * 2) / 1.41
                a = max(0.0, min(1.0, (d - 0.35) / 0.65)) ** 1.6
                pequena.set_at((xx, yy), (24, 0, 48, int(255 * a)))
        v = pygame.transform.smoothscale(pequena, (ancho, alto))
        _CACHE_VINETA.clear()
        _CACHE_VINETA[(ancho, alto)] = v
    return v


def _dibujar_lluvia_de_caras(superficie, ancho, alto, hue_base, nivel, p, tiempo):
    e = _LLUVIA
    if e["dim"] != (ancho, alto):
        e.update(dim=(ancho, alto), caras=[], gotas=_crear_gotas(ancho, alto), t=None)

    objetivo = (
        0
        if nivel < 1 or nivel >= 30
        else int(_CARAS_MIN + p * (_CARAS_MAX - _CARAS_MIN))
    )
    if objetivo == 0:
        e["caras"].clear()
        e["t"] = None
        return

    # Las caras se transforman en el sitio al cambiar de etapa.
    estilo = 0 if p < 0.34 else (1 if p < 0.67 else 2)
    etapa_distorsion = round(p * 9)
    if e["estilo"] != estilo or e["etapa_distorsion"] != etapa_distorsion:
        distorsion = etapa_distorsion / 9
        e["sprites"] = _construir_sprites(estilo, distorsion)
        e["estilo"] = estilo
        e["etapa_distorsion"] = etapa_distorsion

    caras = e["caras"]
    primera = not caras
    while len(caras) < objetivo:
        caras.append(_nueva_cara(ancho, alto, desde_arriba=not primera))
    del caras[objetivo:]

    dt = 1 / 60 if e["t"] is None else max(0.0, min(0.1, tiempo - e["t"]))
    e["t"] = tiempo

    paleta = [_c(hue_base + k / 12 + tiempo * 0.05, 0.8, 1.0) for k in range(12)]
    capa = _obtener_superficie("lluvia", (ancho, alto))

    # Hilos finos de lluvia psicodélica (más densos con el nivel).
    n_gotas = int(_GOTAS_MAX * (0.25 + 0.75 * p))
    for x, y0, vel, largo, k in e["gotas"][:n_gotas]:
        y = (y0 + vel * tiempo) % (alto + largo) - largo
        pygame.draw.line(capa, (*paleta[k], 110), (x, y), (x - largo * 0.15, y + largo), 2)

    # Estela luminosa tras cada cara + actualización de posición.
    for cara in caras:
        cara["y"] += cara["vy"] * dt
        tam, frames = e["sprites"][cara["sprite"]]
        alto_sprite = frames[2].get_height()
        if cara["y"] - alto_sprite / 2 > alto:
            cara.update(_nueva_cara(ancho, alto, desde_arriba=True))
            continue
        x = cara["x"] + math.sin(tiempo * 1.1 + cara["fase"]) * 10
        color = paleta[cara["sprite"] % 12]
        pygame.draw.line(capa, (*color, 70), (x, cara["y"] - alto_sprite * 1.4),
                         (x, cara["y"] - alto_sprite * 0.45), 2)
    superficie.blit(capa, (0, 0))

    # Caras: las lejanas primero para que las cercanas queden delante.
    for cara in sorted(caras, key=lambda c: c["tam"]):
        _, frames = e["sprites"][cara["sprite"]]
        giro = (math.sin(tiempo * 1.5 + cara["fase"]) + 1) / 2
        img = frames[int(giro * (len(frames) - 1) + 0.5)]
        x = cara["x"] + math.sin(tiempo * 1.1 + cara["fase"]) * 10
        superficie.blit(img, img.get_rect(center=(int(x), int(cara["y"]))))


def dibujar_fondo_segmentado(superficie, tiempo, hue_fondo, ancho, alto, nivel=0):
    """Fondo psicodélico que, nivel a nivel, se va llenando de una lluvia de
    caras pensativas que se deforman progresivamente. La lluvia desaparece
    desde el nivel 30."""
    p = max(0.0, min(1.0, (nivel - 1) / 9.0))  # progreso de la transformación
    # El vaivén de color se intensifica con el nivel (más "viaje").
    hue_base = (hue_fondo + math.sin(tiempo * 0.35) * (0.05 + 0.07 * p)) % 1.0
    visible = 1.0 - 0.3 * p  # las manchas se atenúan un poco para dar paso a las caras
    brazos = 6 + 2 * int(p * 3.99)  # el caleidoscopio gana brazos: 6, 8, 10, 12

    _fondo_degradado(superficie, ancho, alto, hue_base, tiempo)
    _dibujar_capas_parallax(superficie, ancho, alto, hue_base, tiempo)

    capa_abstracta = pygame.Surface((ancho, alto), pygame.SRCALPHA)
    _dibujar_caleidoscopio(
        capa_abstracta,
        (ancho * 0.5, alto * 0.5),
        max(ancho, alto) * 0.65,
        hue_base,
        tiempo,
        ancho,
        alto,
        brazos=brazos,
    )
    _puntos_halftone(capa_abstracta, ancho, alto, tiempo, hue_base)

    for i in range(6):
        hue = (hue_base + i / 6 + tiempo * 0.025) % 1.0
        color = color_desde_hue(hue, 0.75, 0.85)
        color_pop = color_desde_hue((hue + 0.5) % 1.0, 0.85, 0.95)
        radio = 150 + i * 42
        centro_x = ancho * (0.18 + (i % 3) * 0.24)
        centro_y = alto * (0.22 + (i % 2) * 0.28)

        margen = 26
        tam = (radio * 2 + margen * 2, radio * 2 + margen * 2)
        capa = _obtener_superficie(("bloque", i), tam)
        centro_local = (radio + margen, radio + margen)

        _mancha_organica(capa, centro_local, radio, color, int(58 * visible), tiempo, i * 1.7, puntos=24, asimetria=0.18)
        _trazo_contorno(capa, centro_local, radio, color_pop, int(80 * visible), tiempo, i * 1.7, grosor=3)
        _trazo_tinta(capa, centro_local, radio, tiempo, i * 1.7, alpha=int(110 * visible), grosor=5)

        rect_local = pygame.Rect(margen, margen, radio * 2, radio * 2)
        pygame.draw.arc(
            capa,
            (*color_pop, int(130 * visible)),
            rect_local.inflate(18, 18),
            math.radians(20 + i * 18 + tiempo * 14),
            math.radians(190 + i * 18 + tiempo * 14),
            12,
        )
        capa_abstracta.blit(capa, (centro_x - radio - margen, centro_y - radio - margen))

        if i % 2 == 0:
            _dibujar_goteo(
                capa_abstracta,
                centro_x + radio * 0.3,
                centro_y + radio * 0.6,
                90 + i * 10,
                (hue + 0.5) % 1.0,
                tiempo,
                fase=i * 2.1,
            )

    for i in range(3):
        hue = (hue_base + 0.18 + i * 0.16 + tiempo * 0.035) % 1.0
        x = (ancho // 3) * (i + 1) - 80
        y = alto // 2 - 100
        radio = 160 + i * 40
        _dibujar_remolino(capa_abstracta, x, y, radio, hue, tiempo, i)

    superficie.blit(capa_abstracta, (0, 0))

    _dibujar_lluvia_de_caras(superficie, ancho, alto, hue_base, nivel, p, tiempo)

    if p > 0:  # viñeta oscura que crece con el nivel
        vineta = _obtener_vineta(ancho, alto)
        vineta.set_alpha(int(170 * p))
        superficie.blit(vineta, (0, 0))