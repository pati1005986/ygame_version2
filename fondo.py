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


def _puntos_halftone(superficie, ancho, alto, tiempo, hue_base, paso=34, alpha=26):
    """Textura de puntos estilo cómic/pop-art (halftone), muy sutil, para que
    el fondo se lea como una lámina impresa en vez de un degradado liso."""
    capa = _obtener_superficie("halftone", (ancho, alto))
    fila = 0
    for y in range(-paso, alto + paso, paso):
        desfase = (paso // 2) if fila % 2 else 0
        for x in range(-paso, ancho + paso, paso):
            cx = x + desfase
            cy = y
            onda = math.sin(cx * 0.01 + tiempo * 0.4) + math.cos(cy * 0.013 - tiempo * 0.3)
            radio_punto = max(1.5, 3.2 + onda * 1.6)
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

    def actualizar(self):
        self.pos.x = (self.pos.x + self.vel.x) % self.ancho
        self.pos.y = (self.pos.y + self.vel.y) % self.alto

    def dibujar(self, superficie, tiempo):
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

        superficie.blit(capa, self.pos - pygame.Vector2(centro))


_VUELTAS_REMOLINO = 2.8
_HILOS_REMOLINO = 4


def _dibujar_remolino(superficie, x, y, radio, hue, tiempo, indice):
    """Espiral con grosor pulsante y goteo final, como una pincelada de acrílico."""
    tam = (radio * 2, radio * 2)
    capa = _obtener_superficie(("remolino", indice), tam)
    centro = pygame.Vector2(radio, radio)
    pasos = min(160, max(60, int(radio * 0.95)))

    for hilo in range(_HILOS_REMOLINO):
        fase_hilo = hilo * (math.tau / _HILOS_REMOLINO)
        anterior = None
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


def dibujar_fondo_segmentado(superficie, tiempo, hue_fondo, ancho, alto):
    """Fondo psicodélico: manchas orgánicas, remolinos con goteo y mandala giratorio."""
    hue_base = (hue_fondo + math.sin(tiempo * 0.35) * 0.05) % 1.0

    # Cielo en degradado en vez de color plano: da profundidad atmosférica
    # antes de apilar las formas caricaturescas encima.
    _fondo_degradado(superficie, ancho, alto, hue_base, tiempo)

    # Mandala de fondo, muy sutil, para dar sensación de movimiento continuo.
    _dibujar_caleidoscopio(
        superficie, (ancho * 0.5, alto * 0.5), max(ancho, alto) * 0.65, hue_base, tiempo, ancho, alto
    )

    # Textura de puntos estilo cómic/pop-art sobre el degradado.
    _puntos_halftone(superficie, ancho, alto, tiempo, hue_base)

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

        # Mancha de bloque con contorno ondulado en vez de elipse perfecta.
        _mancha_organica(capa, centro_local, radio, color, 58, tiempo, i * 1.7, puntos=24, asimetria=0.18)
        _trazo_contorno(capa, centro_local, radio, color_pop, 80, tiempo, i * 1.7, grosor=3)
        _trazo_tinta(capa, centro_local, radio, tiempo, i * 1.7, alpha=110, grosor=5)

        rect_local = pygame.Rect(margen, margen, radio * 2, radio * 2)
        pygame.draw.arc(
            capa,
            (*color_pop, 130),
            rect_local.inflate(18, 18),
            math.radians(20 + i * 18 + tiempo * 14),
            math.radians(190 + i * 18 + tiempo * 14),
            12,
        )
        superficie.blit(capa, (centro_x - radio - margen, centro_y - radio - margen))

        # Goteo ocasional cayendo desde algunos bloques, típico del expresionismo abstracto.
        if i % 2 == 0:
            _dibujar_goteo(
                superficie,
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
        _dibujar_remolino(superficie, x, y, radio, hue, tiempo, i)