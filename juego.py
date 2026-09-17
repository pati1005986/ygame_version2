"""Punto de entrada del juego de plataformas procedural.

El módulo coordina la ventana de Pygame, la generación de niveles, el
personaje y la transición visual. La lógica especializada vive en
``personaje.py`` y ``transicion.py`` para mantener este archivo centrado en
el bucle principal del juego.
"""

import math
import random

import pygame

from personaje import PersonajeHumanoide
from plataformas import Plataforma, color_desde_hue
from transicion import TransicionCaricaturesca

# --------------------------------------------------------------------------
# Configuración general
# --------------------------------------------------------------------------
WIDTH, HEIGHT = 800, 600
FPS = 60

POS_SPAWN = pygame.Vector2(120, 235)  # centro del punto de aparición del jugador

ESTADO_JUGANDO = "jugando"
ESTADO_TRANSICION = "transicion"
ESTADO_GAME_OVER = "game_over"


# --------------------------------------------------------------------------
# Elementos visuales
# --------------------------------------------------------------------------
class ParticulaAbstracta:
    """Mancha de color translúcida que flota lentamente por el fondo,
    convertida en espiral cromática para reforzar la sensación de movimiento
    pictórico y segmentación del paisaje visual."""

    def __init__(self):
        self.pos = pygame.Vector2(random.uniform(0, WIDTH), random.uniform(0, HEIGHT))
        self.radio = random.uniform(30, 95)
        self.hue = random.random()
        self.vel = pygame.Vector2(random.uniform(-0.25, 0.25), random.uniform(-0.15, 0.15))
        self.fase = random.uniform(0, math.tau)
        self.secciones = random.randint(8, 15)
        self.giro = random.uniform(0.7, 1.6)

    def actualizar(self):
        """Mueve la partícula y la devuelve al borde opuesto de la pantalla."""
        self.pos.x = (self.pos.x + self.vel.x) % WIDTH
        self.pos.y = (self.pos.y + self.vel.y) % HEIGHT

    def dibujar(self, superficie, tiempo):
        """Pinta una espiral cromática con varios remolinos de color."""
        hue_base = (self.hue + tiempo * 0.015) % 1.0
        radio = self.radio + math.sin(tiempo * 2 + self.fase) * 6
        capa = pygame.Surface((radio * 2, radio * 2), pygame.SRCALPHA)
        centro = (radio, radio)

        for i in range(self.secciones):
            angulo = self.fase + i * (math.tau / self.secciones) + tiempo * self.giro
            distancia = 5 + i * (radio / self.secciones) * 0.75
            offset = pygame.Vector2(math.cos(angulo), math.sin(angulo)) * distancia
            color = color_desde_hue((hue_base + i / self.secciones * 0.24) % 1.0, 0.65, 0.92)
            radio_punto = max(3, int((radio * 0.18) - i * 0.35))
            pygame.draw.circle(
                capa,
                (*color, 185),
                (int(centro[0] + offset.x), int(centro[1] + offset.y)),
                radio_punto,
            )

        base = color_desde_hue(hue_base, 0.45, 0.85)
        pygame.draw.circle(capa, (*base, 42), centro, int(radio * 0.8), 2)
        superficie.blit(capa, self.pos - pygame.Vector2(radio, radio))




# Caché de superficies reutilizadas entre frames para el fondo segmentado.
# Se crean una sola vez por forma y luego solo se limpian y se vuelven a
# dibujar encima, en vez de crear una Surface nueva cada frame.
_CACHE_FONDO = {}


def _obtener_superficie(clave, tam):
    """Devuelve una Surface SRCALPHA reutilizada del tamaño pedido.
    Solo se crea de nuevo si no existe o si su tamaño cambió."""
    capa = _CACHE_FONDO.get(clave)
    if capa is None or capa.get_size() != tam:
        capa = pygame.Surface(tam, pygame.SRCALPHA)
        _CACHE_FONDO[clave] = capa
    else:
        capa.fill((0, 0, 0, 0))
    return capa


def dibujar_fondo_segmentado(superficie, tiempo, hue_fondo):
    """Genera un fondo con bloques segmentados y remolinos circulares.

    Cada capa se dibuja en una superficie del tamaño justo de su forma
    (no de toda la pantalla) y esas superficies se reciclan de un frame a
    otro, así el costo de memoria no crece aunque los remolinos sean más
    grandes o más detallados.
    """
    hue_base = (hue_fondo + math.sin(tiempo * 0.35) * 0.04) % 1.0
    superficie.fill(color_desde_hue(hue_base, 0.32, 0.9))

    for i in range(6):
        hue = (hue_base + i / 6 + tiempo * 0.02) % 1.0
        color = color_desde_hue(hue, 0.68, 0.82)
        radio = 150 + i * 42
        centro_x = WIDTH * (0.18 + (i % 3) * 0.24)
        centro_y = HEIGHT * (0.22 + (i % 2) * 0.28)

        margen = 18  # espacio extra para que el arco inflado no se recorte
        tam = (radio * 2 + margen * 2, radio * 2 + margen * 2)
        capa = _obtener_superficie(("bloque", i), tam)
        rect_local = pygame.Rect(margen, margen, radio * 2, radio * 2)

        pygame.draw.ellipse(capa, (*color, 44), rect_local)
        pygame.draw.arc(
            capa,
            (*color_desde_hue((hue + 0.18) % 1.0, 0.75, 1.0), 120),
            rect_local.inflate(18, 18),
            math.radians(20 + i * 18 + tiempo * 14),
            math.radians(190 + i * 18 + tiempo * 14),
            12,
        )
        superficie.blit(capa, (centro_x - radio - margen, centro_y - radio - margen))

    for i in range(3):
        hue = (hue_base + 0.18 + i * 0.16 + tiempo * 0.03) % 1.0
        x = (WIDTH // 3) * (i + 1) - 80
        y = HEIGHT // 2 - 100
        radio = 160 + i * 40  # remolinos más grandes que antes (120+30*i)
        _dibujar_remolino(superficie, x, y, radio, hue, tiempo, i)


_VUELTAS_REMOLINO = 2.6  # cuántas vueltas da cada brazo de la espiral
_HILOS_REMOLINO = 3      # brazos entrelazados que forman el remolino


def _dibujar_remolino(superficie, x, y, radio, hue, tiempo, indice):
    """Dibuja una espiral matemática real: una curva de Arquímedes, donde
    la distancia al centro crece de forma lineal y continua con el
    ángulo (``distancia = a + b * angulo``), trazada como una polilínea
    de color degradado en vez de puntos sueltos y desconectados.

    Sale más barato que antes pese a tener mucho más detalle: son solo
    segmentos de línea sobre una Surface que ya está en caché (ver
    ``_obtener_superficie``); no se crea ninguna superficie nueva ni se
    dibujan decenas de círculos superpuestos.
    """
    tam = (radio * 2, radio * 2)
    capa = _obtener_superficie(("remolino", indice), tam)
    centro = pygame.Vector2(radio, radio)

    # Más pasos en radios grandes para que la curva se vea suave, con un
    # techo para que el costo no se dispare si algún día se usa un radio
    # mucho mayor.
    pasos = min(140, max(50, int(radio * 0.85)))

    for hilo in range(_HILOS_REMOLINO):
        fase_hilo = hilo * (math.tau / _HILOS_REMOLINO)
        anterior = None
        for paso in range(pasos + 1):
            t = paso / pasos
            angulo = t * math.tau * _VUELTAS_REMOLINO + fase_hilo + tiempo * (1.2 + indice * 0.4)
            distancia = 8 + t * (radio - 16)
            punto = (
                int(centro.x + math.cos(angulo) * distancia),
                int(centro.y + math.sin(angulo) * distancia),
            )
            if anterior is not None:
                # El color se desliza a lo largo del brazo y entre brazos,
                # y el grosor se afina del centro (grueso) hacia la punta
                # (fino), como el trazo de un remolino pintado a mano.
                color = color_desde_hue(
                    (hue + t * 0.35 + hilo / _HILOS_REMOLINO * 0.15) % 1.0, 0.75, 0.95
                )
                grosor = max(1, int(5 * (1 - t)) + 1)
                pygame.draw.line(capa, (*color, 150), anterior, punto, grosor)
            anterior = punto

    # Núcleo brillante en el centro, a juego con el halo que ya usan las
    # plataformas del resto del juego.
    color_nucleo = color_desde_hue(hue, 0.55, 1.0)
    pygame.draw.circle(capa, (*color_nucleo, 130), centro, max(4, int(radio * 0.05)))

    superficie.blit(capa, (x, y))


# --------------------------------------------------------------------------
# Generación de niveles
# --------------------------------------------------------------------------
def generar_nivel(nivel):
    """Genera las plataformas y los matices de color (fondo y jugador) de un
    nivel. La disposición de las plataformas conserva la misma lógica que
    el original; solo cambia cómo se representan visualmente."""
    """Crea un nivel y devuelve sus plataformas y colores base.

    Args:
        nivel: Número del nivel actual; aumenta gradualmente la cantidad de
            plataformas.

    Returns:
        Una tupla ``(plataformas, hue_fondo, hue_jugador)``.
    """
    plataformas = [Plataforma(50, 300, 150, 20, random.random())]

    cantidad_plataformas = min(6 + nivel // 2, 14)  # ahora sí escala con el nivel
    for _ in range(cantidad_plataformas):
        x = random.randint(0, WIDTH - 100)
        y = random.randint(100, HEIGHT - 50)
        w = random.randint(50, 200)
        h = 20
        if not (x < 200 and 250 < y < 350):  # evita tapar el punto de aparición
            plataformas.append(Plataforma(x, y, w, h, random.random(), random.random() < 0.28))

    hue_fondo = random.random()
    hue_jugador = random.random()
    return plataformas, hue_fondo, hue_jugador


# --------------------------------------------------------------------------
# Juego
# --------------------------------------------------------------------------
def main():
    """Inicializa Pygame y ejecuta el bucle de eventos, física y renderizado."""
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Plataformas Procedurales - Lienzo Abstracto")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 36)
    boton_reintentar = pygame.Rect(WIDTH // 2 - 110, HEIGHT // 2 + 45, 220, 52)

    nivel = 0
    plataformas, hue_fondo, hue_jugador = generar_nivel(nivel)
    particulas = [ParticulaAbstracta() for _ in range(12)]

    jugador = PersonajeHumanoide(*POS_SPAWN, color_desde_hue(hue_jugador))
    jugador.rect.center = POS_SPAWN

    estado = ESTADO_JUGANDO
    transicion = None

    jugando = True
    while jugando:
        clock.tick(FPS)
        tiempo = pygame.time.get_ticks() / 1000.0

        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                jugando = False
            if evento.type == pygame.KEYDOWN:
                if estado == ESTADO_JUGANDO and evento.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                    jugador.saltar()
                elif estado == ESTADO_GAME_OVER and evento.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r):
                    nivel = 0
                    plataformas, hue_fondo, hue_jugador = generar_nivel(nivel)
                    jugador = PersonajeHumanoide(*POS_SPAWN, color_desde_hue(hue_jugador))
                    jugador.rect.center = POS_SPAWN
                    transicion = None
                    estado = ESTADO_JUGANDO
            if (
                evento.type == pygame.MOUSEBUTTONDOWN
                and evento.button == pygame.BUTTON_LEFT
                and estado == ESTADO_GAME_OVER
                and boton_reintentar.collidepoint(evento.pos)
            ):
                nivel = 0
                plataformas, hue_fondo, hue_jugador = generar_nivel(nivel)
                jugador = PersonajeHumanoide(*POS_SPAWN, color_desde_hue(hue_jugador))
                jugador.rect.center = POS_SPAWN
                transicion = None
                estado = ESTADO_JUGANDO

        # Durante la transición se bloquean los controles y solo se actualiza
        # la entrada visual del jugador al nuevo nivel.
        if estado == ESTADO_JUGANDO:
            jugador.mover(plataformas)
            alpha_overlay = 0

            plataforma_pisada = jugador.plataforma_actual
            if jugador.en_suelo and plataforma_pisada is not None and plataforma_pisada.es_trampa:
                plataforma_pisada.activar_trampa()
                jugador.iniciar_engullido(plataforma_pisada)
                estado = ESTADO_GAME_OVER

            salio_de_pantalla = (
                jugador.rect.top > HEIGHT
                or jugador.rect.right < 0
                or jugador.rect.left > WIDTH
                or jugador.rect.bottom < 0
            )
            if salio_de_pantalla:
                nivel += 1
                color_origen = jugador.color
                pos_origen = pygame.Vector2(jugador.rect.center)

                plataformas, hue_fondo, hue_jugador = generar_nivel(nivel)
                color_destino = color_desde_hue(hue_jugador)

                transicion = TransicionCaricaturesca(
                    color_origen,
                    color_destino,
                    pos_origen,
                    POS_SPAWN,
                )
                jugador.vel_y = 0
                estado = ESTADO_TRANSICION

        elif estado == ESTADO_GAME_OVER:
            for plataforma in plataformas:
                plataforma.actualizar()
            if jugador.muriendo:
                jugador.actualizar_engullido()
            elif any(plataforma.trampa_activada for plataforma in plataformas):
                jugador.rect.y += 3

        elif estado == ESTADO_TRANSICION:
            if transicion.actualizar(jugador):
                estado = ESTADO_JUGANDO

        # --- Renderizado ---
        dibujar_fondo_segmentado(screen, tiempo, hue_fondo)

        for particula in particulas:
            particula.actualizar()
            particula.dibujar(screen, tiempo)

        for plataforma in plataformas:
            if estado != ESTADO_GAME_OVER:
                plataforma.actualizar()
            plataforma.dibujar(screen, tiempo, nivel)

        jugador.dibujar(screen)

        if estado == ESTADO_TRANSICION:
            transicion.dibujar(screen)

        panel_texto = pygame.Surface((110, 36), pygame.SRCALPHA)
        panel_texto.fill((0, 0, 0, 90))
        screen.blit(panel_texto, (6, 6))
        texto = font.render(f"Nivel: {nivel}", True, (255, 255, 255))
        screen.blit(texto, (14, 10))

        if estado == ESTADO_GAME_OVER:
            mensaje = font.render("FELICIDADES - la trampa te ha tragado", True, (255, 245, 245))
            screen.blit(mensaje, mensaje.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 25)))

            color_boton = (36, 28, 55)
            if boton_reintentar.collidepoint(pygame.mouse.get_pos()):
                color_boton = (65, 45, 92)
            pygame.draw.rect(screen, color_boton, boton_reintentar, border_radius=8)
            pygame.draw.rect(screen, (255, 245, 245), boton_reintentar, 2, border_radius=8)
            texto_boton = font.render("VOLVER A INTENTAR", True, (255, 255, 255))
            screen.blit(texto_boton, texto_boton.get_rect(center=boton_reintentar.center))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()