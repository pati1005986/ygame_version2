import colorsys
import math
import random

import pygame

from idioma import texto


class MenuPausa:
    """Menu de pausa con estilo caricaturesco y fondo de arte abstracto,
    dibujado sobre el lienzo logico del juego."""

    # Resolucion de referencia sobre la que se disenaron los tamanos
    # originales; el factor de escala se calcula relativo a esto.
    ANCHO_REFERENCIA = 800
    ALTO_REFERENCIA = 600
    ESCALA_MIN = 0.55
    ESCALA_MAX = 1.6

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

    def __init__(self, ancho, alto, idioma="en", escala_ui=1.0):
        self.ancho = ancho
        self.alto = alto
        self.idioma = idioma
        self.escala_ui = escala_ui
        self._tiempo = 0.0
        self._crear_fuentes()
        self._crear_rectangulos()
        self._formas_abstractas = self._generar_formas_abstractas()

    def _escala(self):
        """Factor de escala relativo a la resolucion de referencia, con
        limites para que el texto nunca sea ilegible ni gigante, multiplicado
        por la preferencia de escala de UI del jugador."""
        base = max(
            self.ESCALA_MIN,
            min(
                self.ancho / self.ANCHO_REFERENCIA,
                self.alto / self.ALTO_REFERENCIA,
                self.ESCALA_MAX,
            ),
        )
        return base * self.escala_ui

    def _crear_fuentes(self):
        escala = self._escala()
        self.fuente_titulo = pygame.font.SysFont(
            "comicsansms", max(26, int(56 * escala)), bold=True
        )
        self.fuente_boton = pygame.font.SysFont(
            "comicsansms", max(14, int(24 * escala)), bold=True
        )

    def _crear_rectangulos(self):
        centro = self.ancho // 2

        ancho_boton = int(max(190, min(340, self.ancho * 0.4)))
        alto_boton = int(max(38, min(64, self.alto * 0.1)))
        espacio = max(8, int(alto_boton * 0.28))
        bloque_alto = alto_boton * 3 + espacio * 2

        titulo_y = max(55, int(self.alto * 0.2))
        margen_bajo_titulo = titulo_y + int(alto_boton * 0.85)
        y_maximo = self.alto - bloque_alto - int(self.alto * 0.04)
        y_inicio = min(max(margen_bajo_titulo, int(self.alto * 0.4)), max(margen_bajo_titulo, y_maximo))

        self.titulo_y = titulo_y
        self.boton_continuar = pygame.Rect(centro - ancho_boton // 2, y_inicio, ancho_boton, alto_boton)
        self.boton_opciones = pygame.Rect(
            centro - ancho_boton // 2, y_inicio + alto_boton + espacio, ancho_boton, alto_boton
        )
        self.boton_salir = pygame.Rect(
            centro - ancho_boton // 2, y_inicio + (alto_boton + espacio) * 2, ancho_boton, alto_boton
        )

    def actualizar_tamano(self, ancho, alto):
        self.ancho = ancho
        self.alto = alto
        self._crear_fuentes()
        self._crear_rectangulos()
        self._formas_abstractas = self._generar_formas_abstractas()

    def establecer_idioma(self, idioma):
        self.idioma = idioma

    def establecer_escala_ui(self, escala_ui):
        self.escala_ui = escala_ui
        self._crear_fuentes()
        self._crear_rectangulos()

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

    def _color_arcoiris_pixel(self, x_norm, y_norm, fase):
        """Calcula un color de arcoíris tipo 8-bit para una celda de pixel,
        con bandas diagonales que se desplazan con el tiempo."""
        matiz = (x_norm * 0.55 + y_norm * 0.2 + fase * 0.12) % 1.0
        r, g, b = colorsys.hsv_to_rgb(matiz, 0.9, 1.0)
        return (int(r * 255), int(g * 255), int(b * 255))

    def _generar_textura_boton_pixelada(self, ancho, alto, fase, hover, semilla):
        """Genera la textura arcoíris pixelada de un botón como una superficie
        de baja resolución, lista para escalarse sin suavizado (look 8-bit)."""
        tam_pixel = max(3, alto // 8)
        columnas = max(4, ancho // tam_pixel)
        filas = max(4, alto // tam_pixel)

        lienzo_bajo = pygame.Surface((columnas, filas))
        aleatorio_destellos = random.Random(semilla)

        for fila in range(filas):
            for col in range(columnas):
                en_borde = fila in (0, 1, filas - 2, filas - 1) or col in (0, 1, columnas - 2, columnas - 1)
                if en_borde:
                    lienzo_bajo.set_at((col, fila), self.COLOR_BOTON_BORDE)
                    continue
                x_norm = col / max(1, columnas - 1)
                y_norm = fila / max(1, filas - 1)
                color = self._color_arcoiris_pixel(x_norm, y_norm, fase)
                # franja de "brillo" pixelado tipo comic en la parte superior
                if y_norm < 0.28 and (col + fila) % 3 != 0:
                    color = tuple(min(255, c + 70) for c in color)
                lienzo_bajo.set_at((col, fila), color)

        # destellos blancos tipo "estrellita" 8-bit, más activos con el hover
        num_destellos = 5 if hover else 2
        for _ in range(num_destellos):
            col = aleatorio_destellos.randint(2, columnas - 3)
            fila = aleatorio_destellos.randint(2, filas - 3)
            lienzo_bajo.set_at((col, fila), (255, 255, 255))

        return pygame.transform.scale(lienzo_bajo, (ancho, alto))

    def _dibujar_boton_comic(self, superficie, rect, contenido, hover, fase=0.0):
        """Botón arcoíris pixelado y caricaturesco: relleno tipo 8-bit con
        bandas de color que se desplazan, contorno grueso estilo comic y
        texto con borde negro para máxima legibilidad."""
        escala = 1.0 + (0.06 * math.sin(fase * 6.0) + 0.06 if hover else 0.0)
        ancho_b = int(rect.width * escala)
        alto_b = int(rect.height * escala)
        rect_animado = pygame.Rect(0, 0, ancho_b, alto_b)
        rect_animado.center = rect.center

        desplazamiento_sombra = max(3, int(rect.height * 0.15)) if not hover else max(2, int(rect.height * 0.08))
        rect_sombra = rect_animado.move(desplazamiento_sombra, desplazamiento_sombra)
        pygame.draw.rect(superficie, self.COLOR_BOTON_SOMBRA, rect_sombra)

        velocidad_desfile = 1.4 if hover else 0.7
        semilla_destellos = f"boton-{rect.x}-{rect.y}-{int(fase * (10 if hover else 3))}"
        textura = self._generar_textura_boton_pixelada(
            rect_animado.width,
            rect_animado.height,
            fase * velocidad_desfile,
            hover,
            semilla_destellos,
        )
        superficie.blit(textura, rect_animado.topleft)

        pygame.draw.rect(superficie, self.COLOR_BOTON_BORDE, rect_animado, width=max(2, int(rect_animado.height * 0.075)))

        self._texto_contorno(
            superficie,
            contenido,
            self.fuente_boton,
            rect_animado.center,
            (255, 255, 255),
            self.COLOR_BOTON_BORDE,
            grosor=2,
        )

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
            (self.ancho // 2, self.titulo_y + bamboleo),
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