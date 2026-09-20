import math
import random

import pygame

from idioma import texto


class MenuPausa:
    """Menu de pausa con estilo caricaturesco y fondo de arte abstracto,
    dibujado sobre el lienzo logico del juego."""

    # Paleta tipo comic: colores planos y muy saturados
    COLOR_FONDO_OVERLAY = (20, 10, 40, 170)
    COLOR_TITULO = (255, 221, 87)
    COLOR_TITULO_CONTORNO = (120, 40, 10)

    COLOR_BOTON = (255, 138, 61)
    COLOR_BOTON_HOVER = (255, 179, 71)
    COLOR_BOTON_SOMBRA = (120, 40, 10)
    COLOR_BOTON_BORDE = (40, 20, 10)
    COLOR_TEXTO_BOTON = (40, 20, 10)

    # Paleta de las formas de arte abstracto (RGBA)
    COLORES_ABSTRACTOS = (
        (255, 138, 61, 95),
        (255, 221, 87, 85),
        (130, 90, 255, 85),
        (255, 90, 170, 75),
        (90, 220, 255, 75),
        (80, 220, 140, 75),
    )

    def __init__(self, ancho, alto, idioma="en"):
        self.ancho = ancho
        self.alto = alto
        self.idioma = idioma
        self.fuente_titulo = pygame.font.SysFont("comicsansms", 56, bold=True)
        self.fuente_boton = pygame.font.SysFont("comicsansms", 24, bold=True)
        self._tiempo = 0.0
        self._crear_rectangulos()
        self._formas_abstractas = self._generar_formas_abstractas()

    def _crear_rectangulos(self):
        centro = self.ancho // 2
        self.boton_continuar = pygame.Rect(centro - 150, 245, 300, 54)
        self.boton_opciones = pygame.Rect(centro - 150, 315, 300, 54)
        self.boton_salir = pygame.Rect(centro - 150, 385, 300, 54)

    def actualizar_tamano(self, ancho, alto):
        self.ancho = ancho
        self.alto = alto
        self._crear_rectangulos()
        self._formas_abstractas = self._generar_formas_abstractas()

    def establecer_idioma(self, idioma):
        self.idioma = idioma

    # ---------- arte abstracto de fondo ----------

    def _generar_formas_abstractas(self):
        """Genera una composicion fija (semilla estable) de formas geometricas
        flotantes, tipo collage de arte abstracto."""
        aleatorio = random.Random(f"pausa-{self.ancho}x{self.alto}")
        tipos = ("circulo", "triangulo", "cuadrado", "linea")
        formas = []
        for _ in range(12):
            formas.append(
                {
                    "tipo": aleatorio.choice(tipos),
                    "x": aleatorio.uniform(0, self.ancho),
                    "y": aleatorio.uniform(0, self.alto),
                    "tam": aleatorio.uniform(45, 150),
                    "color": aleatorio.choice(self.COLORES_ABSTRACTOS),
                    "velocidad": aleatorio.uniform(0.25, 0.7),
                    "fase": aleatorio.uniform(0, math.tau),
                    "rotacion": aleatorio.uniform(0, 360),
                    "vel_rotacion": aleatorio.uniform(-18, 18),
                }
            )
        return formas

    def _dibujar_formas_abstractas(self, superficie):
        for forma in self._formas_abstractas:
            tam = forma["tam"]
            offset_x = math.cos(self._tiempo * forma["velocidad"] + forma["fase"]) * 18
            offset_y = math.sin(self._tiempo * forma["velocidad"] * 0.8 + forma["fase"]) * 18
            angulo = forma["rotacion"] + self._tiempo * forma["vel_rotacion"]

            lienzo = pygame.Surface((tam * 2.2, tam * 2.2), pygame.SRCALPHA)
            centro_lienzo = (lienzo.get_width() // 2, lienzo.get_height() // 2)

            if forma["tipo"] == "circulo":
                pygame.draw.circle(lienzo, forma["color"], centro_lienzo, tam / 2)
            elif forma["tipo"] == "cuadrado":
                rect = pygame.Rect(0, 0, tam, tam)
                rect.center = centro_lienzo
                pygame.draw.rect(lienzo, forma["color"], rect, border_radius=12)
            elif forma["tipo"] == "triangulo":
                r = tam / 2
                puntos = [
                    (centro_lienzo[0], centro_lienzo[1] - r),
                    (centro_lienzo[0] - r, centro_lienzo[1] + r),
                    (centro_lienzo[0] + r, centro_lienzo[1] + r),
                ]
                pygame.draw.polygon(lienzo, forma["color"], puntos)
            else:  # linea gruesa tipo trazo de pincel
                pygame.draw.line(
                    lienzo,
                    forma["color"],
                    (centro_lienzo[0] - tam / 2, centro_lienzo[1]),
                    (centro_lienzo[0] + tam / 2, centro_lienzo[1]),
                    max(6, int(tam / 8)),
                )

            lienzo_rotado = pygame.transform.rotate(lienzo, angulo)
            destino = lienzo_rotado.get_rect(
                center=(forma["x"] + offset_x, forma["y"] + offset_y)
            )
            superficie.blit(lienzo_rotado, destino)

    # ---------- utilidades de dibujo "caricaturesco" ----------

    def _texto_contorno(self, superficie, contenido, fuente, centro, color_relleno, color_contorno, grosor=3):
        """Dibuja texto con un contorno grueso, efecto historieta."""
        base = fuente.render(contenido, True, color_contorno)
        for dx in range(-grosor, grosor + 1):
            for dy in range(-grosor, grosor + 1):
                if dx == 0 and dy == 0:
                    continue
                if dx * dx + dy * dy > grosor * grosor:
                    continue
                rect = base.get_rect(center=(centro[0] + dx, centro[1] + dy))
                superficie.blit(base, rect)
        relleno = fuente.render(contenido, True, color_relleno)
        superficie.blit(relleno, relleno.get_rect(center=centro))

    def _texto_centrado(self, superficie, contenido, fuente, centro, color):
        imagen = fuente.render(contenido, True, color)
        superficie.blit(imagen, imagen.get_rect(center=centro))

    def _dibujar_boton_comic(self, superficie, rect, contenido, hover, fase=0.0):
        """Botón más abstracto y multicolor, con capas de color, brillo y formas diagonales."""
        escala = 1.0 + (0.06 * math.sin(fase * 6.0) + 0.06 if hover else 0.0)
        ancho_b = int(rect.width * escala)
        alto_b = int(rect.height * escala)
        rect_animado = pygame.Rect(0, 0, ancho_b, alto_b)
        rect_animado.center = rect.center

        desplazamiento_sombra = 8 if not hover else 4
        rect_sombra = rect_animado.move(desplazamiento_sombra, desplazamiento_sombra)

        radio = 18
        pygame.draw.rect(superficie, self.COLOR_BOTON_SOMBRA, rect_sombra, border_radius=radio)

        capa_boton = pygame.Surface(rect_animado.size, pygame.SRCALPHA)
        paleta = [
            (255, 109, 92),
            (255, 200, 93),
            (99, 224, 173),
            (126, 148, 255),
            (255, 118, 190),
            (90, 220, 255),
            (255, 235, 120),
        ]
        for indice, color in enumerate(paleta):
            ancho = max(14, rect_animado.width // len(paleta) - 2)
            x = 4 + indice * (ancho + 3)
            y = 4 + (indice % 2) * 3
            pygame.draw.rect(capa_boton, (*color, 170 + indice * 8), (x, y, ancho, rect_animado.height - 10), border_radius=radio)

        puntos_abstractos = [
            (0, rect_animado.height * 0.2),
            (rect_animado.width * 0.25, 0),
            (rect_animado.width * 0.72, 0),
            (rect_animado.width, rect_animado.height * 0.36),
            (rect_animado.width, rect_animado.height),
            (rect_animado.width * 0.35, rect_animado.height),
            (0, rect_animado.height * 0.78),
        ]
        pygame.draw.polygon(capa_boton, (255, 255, 255, 35), puntos_abstractos)
        pygame.draw.polygon(capa_boton, (255, 255, 255, 70), [(0, 8), (rect_animado.width * 0.82, 0), (rect_animado.width, rect_animado.height * 0.32), (rect_animado.width * 0.56, rect_animado.height * 0.3)])
        pygame.draw.rect(capa_boton, (255, 255, 255, 48), (8, 5, rect_animado.width - 16, rect_animado.height // 3), border_radius=radio)
        superficie.blit(capa_boton, rect_animado.topleft)

        pygame.draw.rect(superficie, self.COLOR_BOTON_BORDE, rect_animado, width=4, border_radius=radio)

        brillo = pygame.Rect(rect_animado.x + 10, rect_animado.y + 6, rect_animado.width - 20, rect_animado.height // 3)
        superficie_brillo = pygame.Surface(brillo.size, pygame.SRCALPHA)
        superficie_brillo.fill((255, 255, 255, 70))
        superficie.blit(superficie_brillo, brillo.topleft)

        self._texto_centrado(superficie, contenido, self.fuente_boton, rect_animado.center, self.COLOR_TEXTO_BOTON)

    # ---------- dibujo principal ----------

    def dibujar(self, superficie, mouse_pos=None, dt=1 / 60):
        self._tiempo += dt

        self._dibujar_formas_abstractas(superficie)

        capa = pygame.Surface((self.ancho, self.alto), pygame.SRCALPHA)
        capa.fill(self.COLOR_FONDO_OVERLAY)
        superficie.blit(capa, (0, 0))

        bamboleo = math.sin(self._tiempo * 3.0) * 4
        self._texto_contorno(
            superficie,
            texto(self.idioma, "pause"),
            self.fuente_titulo,
            (self.ancho // 2, 145 + bamboleo),
            self.COLOR_TITULO,
            self.COLOR_TITULO_CONTORNO,
            grosor=4,
        )

        botones = (
            (self.boton_continuar, "continue"),
            (self.boton_opciones, "options"),
            (self.boton_salir, "exit"),
        )
        posicion_raton = mouse_pos if mouse_pos is not None else pygame.mouse.get_pos()
        for rect, clave in botones:
            hover = rect.collidepoint(posicion_raton)
            self._dibujar_boton_comic(
                superficie, rect, texto(self.idioma, clave), hover, fase=self._tiempo
            )

    def manejar_evento(self, evento):
        if evento.type == pygame.KEYDOWN and evento.key == pygame.K_ESCAPE:
            return "continuar"
        if evento.type != pygame.MOUSEBUTTONDOWN or evento.button != 1:
            return None
        if self.boton_continuar.collidepoint(evento.pos):
            return "continuar"
        if self.boton_opciones.collidepoint(evento.pos):
            return "opciones"
        if self.boton_salir.collidepoint(evento.pos):
            return "salir"
        return None