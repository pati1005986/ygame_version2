import math
import random

import pygame

from idioma import alternar_idioma, texto


class MenuOpciones:
    """Pantalla independiente para configurar el juego, con estilo
    caricaturesco y fondo de arte abstracto.

    ``configuracion`` se modifica en el sitio para que el bucle principal pueda
    reutilizarla al volver al menu.
    """

    RESOLUCIONES = ((800, 600), (640, 480), (480, 360))
    CONTROLES = ("left", "right", "jump", "down")

    # Paleta tipo comic
    COLOR_FONDO = (24, 14, 46)
    COLOR_TITULO = (255, 221, 87)
    COLOR_TITULO_CONTORNO = (120, 40, 10)

    COLOR_BOTON = (255, 138, 61)
    COLOR_BOTON_HOVER = (255, 179, 71)
    COLOR_BOTON_ACTIVO = (90, 230, 200)
    COLOR_BOTON_SOMBRA = (120, 40, 10)
    COLOR_BOTON_BORDE = (40, 20, 10)
    COLOR_TEXTO_BOTON = (40, 20, 10)

    COLOR_BOTON_CHICO = (130, 90, 255)
    COLOR_BOTON_CHICO_HOVER = (165, 130, 255)

    # Paleta de las formas de arte abstracto (RGBA)
    COLORES_ABSTRACTOS = (
        (255, 138, 61, 90),
        (255, 221, 87, 80),
        (130, 90, 255, 80),
        (255, 90, 170, 70),
        (90, 220, 255, 70),
        (80, 220, 140, 70),
    )

    def __init__(self, ancho, alto, configuracion):
        self.ancho = ancho
        self.alto = alto
        self.configuracion = configuracion
        self.fuente_titulo = pygame.font.SysFont("comicsansms", 44, bold=True)
        self.fuente = pygame.font.SysFont("comicsansms", 22, bold=True)
        self.fuente_pequena = pygame.font.SysFont("comicsansms", 18, bold=True)
        self.tecla_esperada = None
        self._tiempo = 0.0
        self._crear_rectangulos()
        self._formas_abstractas = self._generar_formas_abstractas()

    def _crear_rectangulos(self):
        centro = self.ancho // 2
        self.boton_resolucion = pygame.Rect(centro - 190, 130, 380, 48)
        self.boton_idioma = pygame.Rect(centro - 190, 194, 380, 48)
        self.boton_pantalla = pygame.Rect(centro - 190, 258, 380, 48)
        self.boton_volver = pygame.Rect(centro - 190, self.alto - 72, 180, 48)
        self.boton_guardar = pygame.Rect(centro + 10, self.alto - 72, 180, 48)
        inicio_controles = 325
        self.botones_controles = {
            nombre: pygame.Rect(centro - 190, inicio_controles + indice * 48, 380, 38)
            for indice, nombre in enumerate(self.CONTROLES)
        }

    def actualizar_tamano(self, ancho, alto):
        self.ancho = ancho
        self.alto = alto
        self._crear_rectangulos()
        self._formas_abstractas = self._generar_formas_abstractas()

    def establecer_idioma(self, idioma):
        self.configuracion["idioma"] = idioma

    # ---------- arte abstracto de fondo ----------

    def _generar_formas_abstractas(self):
        """Genera una composicion fija (semilla estable) de formas geometricas
        flotantes, tipo collage de arte abstracto."""
        aleatorio = random.Random(f"opciones-{self.ancho}x{self.alto}")
        tipos = ("circulo", "triangulo", "cuadrado", "linea")
        formas = []
        for _ in range(14):
            formas.append(
                {
                    "tipo": aleatorio.choice(tipos),
                    "x": aleatorio.uniform(0, self.ancho),
                    "y": aleatorio.uniform(0, self.alto),
                    "tam": aleatorio.uniform(40, 140),
                    "color": aleatorio.choice(self.COLORES_ABSTRACTOS),
                    "velocidad": aleatorio.uniform(0.2, 0.6),
                    "fase": aleatorio.uniform(0, math.tau),
                    "rotacion": aleatorio.uniform(0, 360),
                    "vel_rotacion": aleatorio.uniform(-15, 15),
                }
            )
        return formas

    def _dibujar_formas_abstractas(self, superficie):
        for forma in self._formas_abstractas:
            tam = forma["tam"]
            offset_x = math.cos(self._tiempo * forma["velocidad"] + forma["fase"]) * 16
            offset_y = math.sin(self._tiempo * forma["velocidad"] * 0.8 + forma["fase"]) * 16
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

    def _texto_centrado(self, superficie, contenido, fuente, centro, color=(40, 20, 10)):
        imagen = fuente.render(contenido, True, color)
        superficie.blit(imagen, imagen.get_rect(center=centro))

    def _dibujar_boton_comic(self, superficie, rect, contenido, hover=False, activo=False, radio=14):
        """Botón más abstracto y multicolor con capas vivas de color y formas diagonales."""
        desplazamiento_sombra = 6 if not hover else 3
        rect_sombra = rect.move(desplazamiento_sombra, desplazamiento_sombra)
        pygame.draw.rect(superficie, self.COLOR_BOTON_SOMBRA, rect_sombra, border_radius=radio)

        rect_dibujo = rect.move(-3 if hover else 0, -3 if hover else 0)
        capa_boton = pygame.Surface(rect_dibujo.size, pygame.SRCALPHA)
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
            ancho = max(12, rect_dibujo.width // len(paleta) - 2)
            x = 4 + indice * (ancho + 3)
            y = 4 + (indice % 2) * 3
            pygame.draw.rect(capa_boton, (*color, 165 + indice * 8), (x, y, ancho, rect_dibujo.height - 10), border_radius=radio)

        puntos_abstractos = [
            (0, rect_dibujo.height * 0.2),
            (rect_dibujo.width * 0.25, 0),
            (rect_dibujo.width * 0.72, 0),
            (rect_dibujo.width, rect_dibujo.height * 0.36),
            (rect_dibujo.width, rect_dibujo.height),
            (rect_dibujo.width * 0.35, rect_dibujo.height),
            (0, rect_dibujo.height * 0.78),
        ]
        pygame.draw.polygon(capa_boton, (255, 255, 255, 35), puntos_abstractos)
        pygame.draw.polygon(capa_boton, (255, 255, 255, 70), [(0, 8), (rect_dibujo.width * 0.82, 0), (rect_dibujo.width, rect_dibujo.height * 0.32), (rect_dibujo.width * 0.56, rect_dibujo.height * 0.3)])
        if activo:
            pygame.draw.rect(capa_boton, (90, 230, 200, 150), (6, 6, rect_dibujo.width - 12, rect_dibujo.height - 12), border_radius=radio)
        pygame.draw.rect(capa_boton, (255, 255, 255, 48), (8, 5, rect_dibujo.width - 16, rect_dibujo.height // 3), border_radius=radio)
        superficie.blit(capa_boton, rect_dibujo.topleft)

        pygame.draw.rect(superficie, self.COLOR_BOTON_BORDE, rect_dibujo, width=3, border_radius=radio)

        brillo = pygame.Rect(rect_dibujo.x + 8, rect_dibujo.y + 4, max(rect_dibujo.width - 16, 0), rect_dibujo.height // 3)
        superficie_brillo = pygame.Surface(brillo.size, pygame.SRCALPHA)
        superficie_brillo.fill((255, 255, 255, 60))
        superficie.blit(superficie_brillo, brillo.topleft)

        return rect_dibujo

    # ---------- dibujo principal ----------

    def _nombre_tecla(self, nombre):
        return pygame.key.name(self.configuracion["controles"][nombre]).upper()

    def dibujar(self, superficie, mouse_pos=None, dt=1 / 60):
        self._tiempo += dt
        posicion_raton = mouse_pos if mouse_pos is not None else pygame.mouse.get_pos()

        superficie.fill(self.COLOR_FONDO)
        self._dibujar_formas_abstractas(superficie)

        # veladura para que el texto siga siendo legible sobre el arte abstracto
        veladura = pygame.Surface((self.ancho, self.alto), pygame.SRCALPHA)
        veladura.fill((15, 8, 30, 95))
        superficie.blit(veladura, (0, 0))

        idioma = self.configuracion["idioma"]
        bamboleo = math.sin(self._tiempo * 3.0) * 3
        self._texto_contorno(
            superficie,
            texto(idioma, "options"),
            self.fuente_titulo,
            (self.ancho // 2, 55 + bamboleo),
            self.COLOR_TITULO,
            self.COLOR_TITULO_CONTORNO,
            grosor=3,
        )

        resolucion = self.configuracion["resoluciones"][self.configuracion["resolucion"]]
        hover = self.boton_resolucion.collidepoint(posicion_raton)
        rect_dibujo = self._dibujar_boton_comic(superficie, self.boton_resolucion, "", hover)
        self._texto_centrado(
            superficie,
            f"{texto(idioma, 'resolution')}: {resolucion[0]} X {resolucion[1]}",
            self.fuente,
            rect_dibujo.center,
        )

        nombre_idioma_actual = {
            "en": "english",
            "es": "spanish",
            "pt": "portuguese",
            "ru": "russian",
        }.get(idioma, "english")

        hover = self.boton_idioma.collidepoint(posicion_raton)
        rect_dibujo = self._dibujar_boton_comic(superficie, self.boton_idioma, "", hover)
        self._texto_centrado(
            superficie,
            f"{texto(idioma, 'language')}: {texto(idioma, nombre_idioma_actual)}",
            self.fuente,
            rect_dibujo.center,
        )

        modo = "fullscreen" if self.configuracion.get("pantalla_completa", False) else "windowed"
        hover = self.boton_pantalla.collidepoint(posicion_raton)
        rect_dibujo = self._dibujar_boton_comic(superficie, self.boton_pantalla, "", hover)
        self._texto_centrado(
            superficie,
            f"{texto(idioma, 'display_mode')}: {texto(idioma, modo)}",
            self.fuente,
            rect_dibujo.center,
        )

        etiquetas = {
            "left": "move_left",
            "right": "move_right",
            "jump": "jump",
            "down": "crouch",
        }
        for nombre in self.CONTROLES:
            rect = self.botones_controles[nombre]
            etiqueta = f"{texto(idioma, etiquetas[nombre])}: {self._nombre_tecla(nombre)}"
            activo = self.tecla_esperada == nombre
            hover = rect.collidepoint(posicion_raton)
            rect_dibujo = self._dibujar_boton_comic(superficie, rect, "", hover, activo=activo, radio=10)
            self._texto_centrado(superficie, etiqueta, self.fuente_pequena, rect_dibujo.center)

        if self.tecla_esperada:
            self._texto_contorno(
                superficie,
                texto(idioma, "press_key"),
                self.fuente_pequena,
                (self.ancho // 2, 305),
                (255, 221, 87),
                (90, 40, 10),
                grosor=2,
            )

        for rect, clave in ((self.boton_volver, "back"), (self.boton_guardar, "apply")):
            hover = rect.collidepoint(posicion_raton)
            rect_dibujo = self._dibujar_boton_comic(superficie, rect, "", hover)
            self._texto_centrado(superficie, texto(idioma, clave), self.fuente, rect_dibujo.center)

    def manejar_evento(self, evento):
        if self.tecla_esperada:
            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_ESCAPE:
                    self.tecla_esperada = None
                else:
                    self.configuracion["controles"][self.tecla_esperada] = evento.key
                    self.tecla_esperada = None
            return None

        if evento.type == pygame.KEYDOWN and evento.key == pygame.K_ESCAPE:
            return "volver"
        if evento.type != pygame.MOUSEBUTTONDOWN or evento.button != 1:
            return None

        if self.boton_resolucion.collidepoint(evento.pos):
            self.configuracion["resolucion"] = (
                self.configuracion["resolucion"] + 1
            ) % len(self.RESOLUCIONES)
        elif self.boton_idioma.collidepoint(evento.pos):
            self.configuracion["idioma"] = alternar_idioma(self.configuracion["idioma"])
        elif self.boton_pantalla.collidepoint(evento.pos):
            self.configuracion["pantalla_completa"] = not self.configuracion.get("pantalla_completa", False)
        elif self.boton_volver.collidepoint(evento.pos):
            return "volver"
        elif self.boton_guardar.collidepoint(evento.pos):
            return "aplicar"
        else:
            for nombre, rect in self.botones_controles.items():
                if rect.collidepoint(evento.pos):
                    self.tecla_esperada = nombre
                    break
        return None