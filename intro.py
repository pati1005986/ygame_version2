"""Animación de entrada del modo infinito.

- A color (la paleta del pasillo cambia de tono sin parar).
- El pasillo y la carrera continúan hasta que termina la secuencia.
- Siempre en modo desenfreno (``euforico = True``).
- Secuencia: apertura en iris, título que rebota, zoom y barras de cine.

La clase ``IntroInfinito`` dibuja en una superficie existente y no toma
control de la ventana ni del bucle principal.
"""
import colorsys
import math
import random

import pygame

from personaje import PersonajeHumanoide

ANCHO, ALTO = 640, 480
FPS = 60
ESCALA_PERSONAJE = 2.0
PIE_Y = 440

N_SEGMENTOS = 24
FILAS = 6
MEDIO_ANCHO = 380
ALTO_TECHO = 260
ALTO_SUELO = 270
JITTER = 1.2
CUADROS_HERVIDO = 5             # las líneas "hierven" a 12 Hz; el movimiento va a 60 fps

COLOR_PERSONAJE = (238, 108, 60)
NIEBLA = (255, 246, 214)
CONTORNO = (22, 10, 36)

# Línea de tiempo de la intro (segundos)
T_ARRANQUE = 0.5      # el personaje empieza a correr
T_IRIS = (0.15, 1.5)  # apertura en iris
T_TITULO = (1.0, 4.0)  # el título aparece (pop) y se mantiene
T_SALIDA = 0.8        # duración de la salida del título
T_ZOOM = 4.5          # fin del zoom inicial
T_BARRAS = (3.8, 4.8)  # las barras de cine se retiran
ALTO_BARRA = 58


# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------
class _Suelo:
    def __init__(self, rect):
        self.rect = rect


class _TeclasAutomaticas:
    """Sustituye al teclado: mantiene D pulsada cuando el personaje corre."""

    def __init__(self):
        self.corre = False

    def __getitem__(self, tecla):
        return self.corre and tecla == pygame.K_d


def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


def mezclar(c1, c2, f):
    return (
        int(c1[0] + (c2[0] - c1[0]) * f),
        int(c1[1] + (c2[1] - c1[1]) * f),
        int(c1[2] + (c2[2] - c1[2]) * f),
    )


def suave(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def rebote(x):
    """Ease-out-back: se pasa un poco y vuelve (efecto de dibujo animado)."""
    x = max(0.0, min(1.0, x))
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def _jitter(a, b, semilla):
    h = (a * 73856093) ^ (b * 19349663) ^ (semilla * 83492791)
    dx = ((h & 0xFFFF) / 0xFFFF - 0.5) * 2 * JITTER
    h2 = (a * 19349663) ^ (b * 83492791) ^ (semilla * 73856093)
    dy = ((h2 & 0xFFFF) / 0xFFFF - 0.5) * 2 * JITTER
    return dx, dy


def paleta(t):
    """Colores del pasillo; el tono gira solo, así que nunca se repite igual."""
    h = (t * 0.06) % 1.0
    return {
        "pared": (hsv(h, 0.55, 0.98), hsv(h, 0.62, 0.64)),
        "techo": (hsv(h + 0.12, 0.50, 0.92), hsv(h + 0.12, 0.58, 0.62)),
        "suelo": (hsv(h + 0.55, 0.65, 0.46), hsv(h + 0.55, 0.72, 0.27)),
    }


# ----------------------------------------------------------------------
# Pasillo infinito en perspectiva
# ----------------------------------------------------------------------
class Pasillo:
    def __init__(self):
        self.avance = 0.0
        self.cuenta = 0

    def avanzar(self, delta):
        self.avance += delta
        while self.avance >= 1.0:
            self.avance -= 1.0
            self.cuenta += 1

    def dibujar(self, s, cx, cy, semilla, pal):
        puntos = []
        for k in range(N_SEGMENTOS + 1):
            z = max(0.3, 0.8 + (k - self.avance) * 0.7)
            gk = k + self.cuenta
            lados = []
            for lado, signo in ((0, -1), (1, 1)):
                x = cx + signo * MEDIO_ANCHO / z
                y_arriba = cy - ALTO_TECHO / z
                y_abajo = cy + ALTO_SUELO / z
                linea = []
                for r in range(FILAS + 1):
                    y = y_arriba + (y_abajo - y_arriba) * r / FILAS
                    dx, dy = _jitter(gk, r + lado * 20, semilla)
                    linea.append((x + dx, y + dy))
                lados.append(linea)
            puntos.append(lados)

        lejos = puntos[N_SEGMENTOS]
        pygame.draw.polygon(
            s, (255, 252, 230),
            [lejos[0][0], lejos[1][0], lejos[1][FILAS], lejos[0][FILAS]],
        )

        for k in range(N_SEGMENTOS - 1, -1, -1):
            gk = k + self.cuenta
            niebla = (k / N_SEGMENTOS) ** 1.5 * 0.75
            a, b = puntos[k], puntos[k + 1]

            c = mezclar(pal["techo"][gk % 2], NIEBLA, niebla)
            quad = [a[0][0], b[0][0], b[1][0], a[1][0]]
            pygame.draw.polygon(s, c, quad)
            pygame.draw.polygon(s, CONTORNO, quad, 2)

            c = mezclar(pal["suelo"][gk % 2], NIEBLA, niebla)
            quad = [a[0][FILAS], b[0][FILAS], b[1][FILAS], a[1][FILAS]]
            pygame.draw.polygon(s, c, quad)
            pygame.draw.polygon(s, CONTORNO, quad, 2)

            for lado in (0, 1):
                for r in range(FILAS):
                    c = mezclar(pal["pared"][(gk + r) % 2], NIEBLA, niebla)
                    quad = [a[lado][r], b[lado][r], b[lado][r + 1], a[lado][r + 1]]
                    pygame.draw.polygon(s, c, quad)
                    pygame.draw.polygon(s, CONTORNO, quad, 2)


def lineas_de_velocidad(s, cx, cy, intensidad):
    for _ in range(int(16 * intensidad)):
        ang = random.uniform(0, math.tau)
        r1 = random.uniform(110, 230)
        r2 = r1 + random.uniform(110, 280)
        p1 = (cx + math.cos(ang) * r1, cy + math.sin(ang) * r1 * 0.9)
        p2 = (cx + math.cos(ang) * r2, cy + math.sin(ang) * r2 * 0.9)
        pygame.draw.line(s, (255, 255, 255), p1, p2, random.randint(1, 3))


# ----------------------------------------------------------------------
# Texto de la intro
# ----------------------------------------------------------------------
def texto_contorneado(fuente, texto, color, grosor=4):
    base = fuente.render(texto, True, color)
    oscuro = fuente.render(texto, True, CONTORNO)
    w, h = base.get_size()
    surf = pygame.Surface((w + grosor * 2, h + grosor * 2), pygame.SRCALPHA)
    for dx in (-grosor, 0, grosor):
        for dy in (-grosor, 0, grosor):
            if dx or dy:
                surf.blit(oscuro, (grosor + dx, grosor + dy))
    surf.blit(base, (grosor, grosor))
    return surf


def iris(s, t):
    """Apertura en iris clásica de dibujo animado."""
    ini, fin = T_IRIS
    if t >= fin:
        return
    q = suave((t - ini) / (fin - ini))
    radio = int(q * 430)
    capa = pygame.Surface((ANCHO, ALTO))
    capa.fill((0, 0, 0))
    capa.set_colorkey((255, 0, 255))
    if radio > 0:
        pygame.draw.circle(capa, (255, 0, 255), (ANCHO // 2, int(ALTO * 0.62)), radio)
    s.blit(capa, (0, 0))


def barras(s, t):
    ini, fin = T_BARRAS
    alto = int(ALTO_BARRA * (1 - suave((t - ini) / (fin - ini))))
    if alto > 0:
        pygame.draw.rect(s, (0, 0, 0), (0, 0, ANCHO, alto))
        pygame.draw.rect(s, (0, 0, 0), (0, ALTO - alto, ANCHO, alto))


def crear_vineta():
    v = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
    v.fill((10, 0, 20, 150))
    pasos = 40
    for i in range(pasos):
        f = 1.45 - 0.75 * i / pasos
        w, h = int(ANCHO * f), int(ALTO * f)
        alfa = int(150 * (1 - i / pasos) ** 1.6)
        pygame.draw.ellipse(
            v, (10, 0, 20, alfa), pygame.Rect((ANCHO - w) // 2, (ALTO - h) // 2, w, h)
        )
    return v


class IntroInfinito:
    """Secuencia visual no bloqueante para el modo infinito."""

    MINI_W, MINI_H = 220, 260
    SUELO_Y = 230
    CENTRO_MINI_X = 110
    DURACION = T_BARRAS[1] + 0.2

    def __init__(self, color=COLOR_PERSONAJE, volumen_efectos=0.8, titulo="INFINITE"):
        self.color = color
        self.volumen_efectos = volumen_efectos
        self.titulo = titulo
        self.superficie_personaje = pygame.Surface(
            (self.MINI_W, self.MINI_H), pygame.SRCALPHA
        )
        self.suelo = _Suelo(pygame.Rect(-4000, self.SUELO_Y, 9000, 80))
        self.vineta = crear_vineta()
        self.lienzo = pygame.Surface((ANCHO, ALTO))
        self.teclas = _TeclasAutomaticas()
        self.fuente_titulo = pygame.font.Font(None, 64)
        self.fuente_titulo.set_bold(True)
        while self.fuente_titulo.size(self.titulo)[0] > ANCHO - 80:
            tamano = self.fuente_titulo.get_height() - 2
            self.fuente_titulo = pygame.font.Font(None, tamano)
            self.fuente_titulo.set_bold(True)
        self.texto_titulo = texto_contorneado(
            self.fuente_titulo, self.titulo, (255, 238, 120), 5
        )
        self.reiniciar()

    @property
    def terminada(self):
        return self.tiempo >= self.DURACION

    def reiniciar(self):
        self.tiempo = 0.0
        self.cuadro = 0
        self.semilla = 0
        self.pasillo = Pasillo()
        self.jugador = PersonajeHumanoide(
            90, 100, self.color, volumen_efectos=self.volumen_efectos
        )
        self.jugador.euforico = True

    def actualizar(self, dt):
        if self.terminada:
            return
        self.tiempo += max(0.0, dt)
        self.teclas.corre = self.tiempo >= T_ARRANQUE
        self.jugador.euforico = True
        self.jugador.mover([self.suelo], estado_teclas=self.teclas)
        self.jugador.rect.centerx = self.CENTRO_MINI_X
        ritmo = abs(self.jugador.vel_x) / self.jugador.velocidad
        self.pasillo.avanzar(0.085 * ritmo)
        if self.cuadro % CUADROS_HERVIDO == 0:
            self.semilla = random.randint(0, 10_000)
        self.cuadro += 1

    def dibujar(self, superficie):
        t = self.tiempo
        jugador = self.jugador
        ritmo = abs(jugador.vel_x) / jugador.velocidad
        cx = ANCHO / 2 + math.sin(t * 5.3) * 14 * ritmo
        cy = ALTO * 0.40 - jugador.bob_actual * 2.5 + math.sin(t * 9.0) * 4 * ritmo

        self.lienzo.fill(NIEBLA)
        self.pasillo.dibujar(self.lienzo, cx, cy, self.semilla, paleta(t))
        lineas_de_velocidad(self.lienzo, cx, cy, ritmo)

        self.superficie_personaje.fill((0, 0, 0, 0))
        jugador.dibujar(self.superficie_personaje)
        tam = (
            int(self.MINI_W * ESCALA_PERSONAJE),
            int(self.MINI_H * ESCALA_PERSONAJE),
        )
        grande = pygame.transform.scale(self.superficie_personaje, tam)
        self.lienzo.blit(
            grande,
            (
                ANCHO / 2 - self.CENTRO_MINI_X * ESCALA_PERSONAJE,
                PIE_Y - self.SUELO_Y * ESCALA_PERSONAJE,
            ),
        )

        zoom = 1.07 + 0.40 * (1 - suave(t / T_ZOOM))
        pulso = max(0.0, 1 - ((t * 2.0) % 1.0) * 3)
        zoom += 0.025 * pulso * ritmo
        angulo = math.sin(t * 4.1) * 2.4 * ritmo
        girado = pygame.transform.rotozoom(self.lienzo, angulo, zoom)
        cuadro = pygame.Surface((ANCHO, ALTO))
        cuadro.blit(girado, girado.get_rect(center=(ANCHO // 2, ALTO // 2)))
        cuadro.blit(self.vineta, (0, 0))

        dt_titulo = t - T_TITULO[0]
        if 0 <= dt_titulo < T_TITULO[1] - T_TITULO[0]:
            entrada = suave(dt_titulo / T_SALIDA)
            salida = suave(
                (T_TITULO[1] - T_TITULO[0] - dt_titulo) / T_SALIDA
            )
            escala = max(0.05, rebote(min(1.0, dt_titulo / 0.35)) * salida)
            titulo = pygame.transform.rotozoom(self.texto_titulo, 0, escala)
            titulo.set_alpha(int(255 * entrada * salida))
            cuadro.blit(titulo, titulo.get_rect(center=(ANCHO // 2, 110)))

        dt_flash = t - T_TITULO[0]
        if 0 <= dt_flash < 0.25:
            flash = pygame.Surface((ANCHO, ALTO))
            flash.fill((255, 255, 255))
            flash.set_alpha(int(170 * (1 - dt_flash / 0.25)))
            cuadro.blit(flash, (0, 0))

        barras(cuadro, t)
        iris(cuadro, t)
        if superficie.get_size() == (ANCHO, ALTO):
            superficie.blit(cuadro, (0, 0))
        else:
            pygame.transform.scale(cuadro, superficie.get_size(), superficie)


def main():
    """Ejecuta la intro de forma independiente para poder previsualizarla."""
    pygame.init()
    pantalla = pygame.display.set_mode((ANCHO, ALTO))
    pygame.display.set_caption("MODO INFINITO")
    reloj = pygame.time.Clock()
    intro = IntroInfinito()
    ejecutando = True
    while ejecutando:
        dt = min(reloj.tick(FPS) / 1000.0, 0.1)
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT or (
                evento.type == pygame.KEYDOWN and evento.key == pygame.K_ESCAPE
            ):
                ejecutando = False
            elif evento.type == pygame.KEYDOWN and evento.key == pygame.K_r:
                intro.reiniciar()
            elif evento.type == pygame.KEYDOWN and evento.key == pygame.K_SPACE:
                intro.jugador.solicitar_salto()
            elif evento.type == pygame.KEYUP and evento.key == pygame.K_SPACE:
                intro.jugador.soltar_salto()
        intro.actualizar(dt)
        intro.dibujar(pantalla)
        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    main()