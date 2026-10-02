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

    # Paleta retro arcade: colores oscuros con luz neon y sensación CRT
    COLOR_FONDO_OVERLAY = (10, 12, 26, 190)
    COLOR_TITULO = (255, 228, 102)
    COLOR_TITULO_CONTORNO = (20, 20, 32)

    # Paleta arcade: primarios de máquina recreativa con neón brillante.
    PALETA_BOTONES = (
        (0, 255, 204),    # cyan arcade
        (255, 214, 51),   # amarillo arcade
        (255, 90, 120),   # magenta/neón
        (110, 160, 255),  # azul de tablero
        (140, 255, 100),  # verde láser
    )
    COLOR_TINTA = (10, 10, 18)           # contorno muy oscuro, estilo gabinete
    COLOR_SOMBRA_STICKER = (5, 8, 18)   # sombra dura de marco arcade
    COLOR_DORSO_STICKER = (210, 225, 255)  # esquina brillante para destacar

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

        panel_ancho = max(ancho_boton + 86, int(self.ancho * 0.52))
        panel_alto = bloque_alto + 84
        panel_top = max(40, y_inicio - 58)
        panel_left = centro - panel_ancho // 2
        self.panel_rect = pygame.Rect(panel_left, panel_top, panel_ancho, panel_alto)

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

    def _dibujar_panel_pausa(self, superficie):
        panel = self.panel_rect.copy()
        sombra = panel.move(16, 16)
        sombra = sombra.inflate(12, 10)
        pygame.draw.rect(superficie, (4, 7, 18), sombra, border_radius=18)

        panel_suave = pygame.Surface((panel.width, panel.height), pygame.SRCALPHA)
        pygame.draw.rect(panel_suave, (15, 20, 40, 210), panel_suave.get_rect(), border_radius=18)
        pygame.draw.rect(panel_suave, (255, 214, 51, 170), panel_suave.get_rect(), width=4, border_radius=18)
        superficie.blit(panel_suave, panel.topleft)

        # Línea de escaneo estilo CRT para sensación de gabinete retro.
        for y in range(panel.top + 16, panel.bottom, 6):
            pygame.draw.rect(superficie, (255, 255, 255, 14), pygame.Rect(panel.left + 16, y, panel.width - 32, 2))

        for x in range(panel.left + 18, panel.right - 20, 28):
            pygame.draw.line(superficie, (96, 120, 255, 110), (x, panel.top + 14), (x, panel.bottom - 14), 2)

        for x in range(panel.left + 30, panel.right - 30, 32):
            for y in range(panel.top + 30, panel.bottom - 20, 30):
                if (x + y) % 3 == 0:
                    pygame.draw.circle(superficie, (255, 214, 51, 90), (x, y), 2)

    def _dibujar_titulo_pausa(self, superficie):
        centro = (self.ancho // 2, self.titulo_y)
        bamboleo = math.sin(self._tiempo * 3.0) * 4
        centro = (centro[0], centro[1] + bamboleo)

        # Rayita tipo arcade con brillo neón.
        linea = pygame.Rect(self.ancho // 2 - 130, self.titulo_y + 38, 260, 8)
        pygame.draw.rect(superficie, (0, 255, 204), linea, border_radius=5)
        pygame.draw.rect(superficie, (255, 214, 51), linea.inflate(-10, -2), border_radius=4)

        self._texto_contorno(
            superficie,
            texto(self.idioma, "pause"),
            self.fuente_titulo,
            centro,
            self.COLOR_TITULO,
            self.COLOR_TITULO_CONTORNO,
            grosor=4,
        )

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

    def _puntos_garabateados(self, rect, fase, semilla, amplitud=1.4, segmentos=3):
        """Devuelve los puntos de un rectangulo con bordes "temblorosos" a
        mano en vez de lineas perfectas: la base del estilo comic
        independiente/fanzine, con temblor estable por boton pero vivo
        gracias a la fase (tiempo)."""
        aleatorio = random.Random(semilla)
        esquinas = [
            (rect.left, rect.top),
            (rect.right, rect.top),
            (rect.right, rect.bottom),
            (rect.left, rect.bottom),
        ]
        puntos = []
        for i in range(4):
            x0, y0 = esquinas[i]
            x1, y1 = esquinas[(i + 1) % 4]
            fase_arista = aleatorio.uniform(0, math.tau)
            vertical = x0 == x1
            for s in range(segmentos):
                t = s / segmentos
                x = x0 + (x1 - x0) * t
                y = y0 + (y1 - y0) * t
                offset = math.sin(fase * 2.1 + fase_arista + t * 6.0) * amplitud
                if vertical:
                    x += offset
                else:
                    y += offset
                puntos.append((x, y))
        return puntos

    def _rotar_punto(self, punto, centro, angulo_grados):
        angulo = math.radians(angulo_grados)
        dx, dy = punto[0] - centro[0], punto[1] - centro[1]
        cos_a, sin_a = math.cos(angulo), math.sin(angulo)
        return (centro[0] + dx * cos_a - dy * sin_a, centro[1] + dx * sin_a + dy * cos_a)

    def _dibujar_relleno_halftone(self, superficie, puntos, color_base):
        """Relleno plano tipo poster con una trama de puntos (Ben-Day) hacia
        la esquina inferior-derecha para sugerir volumen, y un brillo
        triangular de "sticker" en la esquina superior-izquierda."""
        pygame.draw.polygon(superficie, color_base, puntos)

        min_x = min(p[0] for p in puntos)
        min_y = min(p[1] for p in puntos)
        max_x = max(p[0] for p in puntos)
        max_y = max(p[1] for p in puntos)
        interior = pygame.Rect(min_x, min_y, max_x - min_x, max_y - min_y).inflate(-5, -5)
        if interior.width < 6 or interior.height < 6:
            return

        color_trama = tuple(max(0, int(c * 0.6)) for c in color_base)
        espaciado = max(5, interior.height // 5)
        radio = max(1, espaciado * 0.26)
        fila = 0
        y = interior.top
        while y < interior.bottom:
            x = interior.left + (espaciado // 2 if fila % 2 else 0)
            while x < interior.right:
                if (x - interior.left) + (y - interior.top) > (interior.width + interior.height) * 0.34:
                    pygame.draw.circle(superficie, color_trama, (int(x), int(y)), radio)
                x += espaciado
            y += espaciado
            fila += 1

        brillo = pygame.Surface((interior.width, interior.height), pygame.SRCALPHA)
        puntos_brillo = [
            (0, interior.height * 0.42),
            (interior.width * 0.5, 0),
            (interior.width * 0.2, 0),
            (0, interior.height * 0.18),
        ]
        pygame.draw.polygon(brillo, (255, 255, 255, 75), puntos_brillo)
        superficie.blit(brillo, interior.topleft)

    def _dibujar_esquina_pelada(self, superficie, rect, hover):
        """Pequeña esquina de sticker despegandose, para el toque
        "alternativo" de collage de fanzine."""
        tam = 15 if hover else 9
        x, y = rect.right - 2, rect.top + 2
        flap = [(x, y), (x - tam, y), (x, y + tam)]
        pygame.draw.polygon(superficie, self.COLOR_SOMBRA_STICKER, [(p[0] + 1, p[1] + 1) for p in flap])
        pygame.draw.polygon(superficie, self.COLOR_DORSO_STICKER, flap)
        pygame.draw.line(superficie, self.COLOR_TINTA, (x - tam, y), (x, y + tam), 1)

    def _dibujar_salpicadura(self, superficie, rect, fase):
        """Motitas de pintura en aerosol alrededor del boton al pasar el
        mouse, como un sticker recien pegado en una pared de fanzine."""
        aleatorio = random.Random(f"splash-{rect.x}-{rect.y}-{int(fase * 6)}")
        color = random.Random(f"splashcolor-{rect.x}-{rect.y}").choice(self.PALETA_BOTONES)
        for _ in range(5):
            angulo = aleatorio.uniform(0, math.tau)
            distancia = aleatorio.uniform(rect.width * 0.4, rect.width * 0.6)
            x = rect.centerx + math.cos(angulo) * distancia
            y = rect.centery + math.sin(angulo) * distancia * 0.55
            radio = aleatorio.uniform(1.4, 3.2)
            pygame.draw.circle(superficie, color, (int(x), int(y)), radio)

    def _dibujar_boton_comic(self, superficie, rect, contenido, hover, fase=0.0):
        """Botón estilo cómic-punk/fanzine: relleno plano con trama de
        puntos, contorno "dibujado a mano" con temblor, sombra dura de
        sticker despegado y texto con borde negro para máxima legibilidad."""
        indice_color = (rect.x * 7 + rect.y * 13) % len(self.PALETA_BOTONES)
        color_base = self.PALETA_BOTONES[indice_color]
        if hover:
            color_base = tuple(min(255, int(c * 1.12) + 8) for c in color_base)

        amplitud = 2.6 if hover else 1.3
        velocidad = 2.4 if hover else 1.0
        semilla = f"boton-{rect.x}-{rect.y}"
        puntos = self._puntos_garabateados(rect, fase * velocidad, semilla, amplitud=amplitud)

        elevacion = -4 if hover else 0
        puntos = [(x, y + elevacion) for x, y in puntos]

        despl_sombra = (4, 5) if hover else (7, 8)
        angulo_sombra = 2.5 if hover else 4.0
        centro = (rect.centerx, rect.centery + elevacion)
        puntos_sombra = [self._rotar_punto(p, centro, angulo_sombra) for p in puntos]
        puntos_sombra = [(x + despl_sombra[0], y + despl_sombra[1]) for x, y in puntos_sombra]
        pygame.draw.polygon(superficie, self.COLOR_SOMBRA_STICKER, puntos_sombra)

        self._dibujar_relleno_halftone(superficie, puntos, color_base)
        pygame.draw.polygon(superficie, self.COLOR_TINTA, puntos, width=max(2, int(rect.height * 0.09)))

        rect_centro = pygame.Rect(rect.left, rect.top + elevacion, rect.width, rect.height)
        if rect.width >= 90:
            self._dibujar_esquina_pelada(superficie, rect_centro, hover)
        if hover:
            self._dibujar_salpicadura(superficie, rect_centro, fase)

        self._texto_contorno(
            superficie,
            contenido,
            self.fuente_boton,
            rect_centro.center,
            (255, 255, 255),
            self.COLOR_TINTA,
            grosor=2,
        )

    # ---------- dibujo principal ----------

    def dibujar(self, superficie, mouse_pos=None, dt=1 / 60):
        self._tiempo += dt

        self._dibujar_formas_abstractas(superficie)

        capa = pygame.Surface((self.ancho, self.alto), pygame.SRCALPHA)
        capa.fill(self.COLOR_FONDO_OVERLAY)
        superficie.blit(capa, (0, 0))

        self._dibujar_panel_pausa(superficie)
        self._dibujar_titulo_pausa(superficie)

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