import json
import math
import os
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
    # Valores cicleables del slider de escala de UI: independiente de la
    # resolucion de ventana, multiplica el tamano de fuentes y botones de
    # los tres menus (inicio, pausa, opciones).
    ESCALAS_UI = (0.75, 0.85, 1.0, 1.15, 1.3, 1.5)

    ANCHO_REFERENCIA = 800
    ALTO_REFERENCIA = 600
    ESCALA_MIN = 0.5
    ESCALA_MAX = 1.6

    DEFAULTS = {
        "resolucion": 0,
        "pantalla_completa": False,
        "idioma": "en",
        "volumen_musica": 0.8,
        "volumen_efectos": 0.8,
        "escala_ui": 1.0,
        "controles": {
            "left": pygame.K_a,
            "right": pygame.K_d,
            "jump": pygame.K_SPACE,
            "down": pygame.K_s,
        },
    }

    # Paleta tipo comic
    COLOR_FONDO = (24, 14, 46)
    COLOR_TITULO = (255, 221, 87)
    COLOR_TITULO_CONTORNO = (120, 40, 10)

    # Paleta "punk-fanzine": colores plancha de poster, nada de degradados
    # arcoiris. Cada boton toma un color estable de aqui segun su posicion.
    PALETA_BOTONES = (
        (255, 61, 127),   # rosa neon
        (198, 255, 61),   # verde lima acido
        (61, 217, 255),   # cian electrico
        (255, 145, 41),   # naranja blaze
        (167, 96, 255),   # violeta zap
    )
    COLOR_BOTON_ACTIVO = (90, 230, 200)  # pulso cian: "esperando tecla"
    COLOR_TINTA = (24, 18, 24)           # "marcador" negro calido del contorno
    COLOR_SOMBRA_STICKER = (10, 6, 12)   # sombra dura, sin difuminado
    COLOR_DORSO_STICKER = (235, 235, 225)  # reverso de la esquina despegada

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
        for clave, valor in self.DEFAULTS.items():
            if clave == "controles":
                self.configuracion.setdefault("controles", valor.copy())
                for nombre, tecla in valor.items():
                    self.configuracion["controles"].setdefault(nombre, tecla)
            else:
                self.configuracion.setdefault(clave, valor)
        self.tecla_esperada = None
        self._tiempo = 0.0
        self._crear_fuentes()
        self._crear_rectangulos()
        self._formas_abstractas = self._generar_formas_abstractas()

    def _escala(self):
        """Factor de escala relativo a la resolucion de referencia, con
        limites para que el texto nunca sea ilegible ni gigante, multiplicado
        por la preferencia de escala de UI del jugador (independiente de la
        resolucion de ventana elegida)."""
        base = max(
            self.ESCALA_MIN,
            min(
                self.ancho / self.ANCHO_REFERENCIA,
                self.alto / self.ALTO_REFERENCIA,
                self.ESCALA_MAX,
            ),
        )
        escala_ui = self.configuracion.get("escala_ui", 1.0)
        return base * escala_ui

    def _crear_fuentes(self):
        escala = self._escala()
        self.fuente_titulo = pygame.font.SysFont(
            "comicsansms", max(22, int(44 * escala)), bold=True
        )
        self.fuente = pygame.font.SysFont("comicsansms", max(12, int(22 * escala)), bold=True)
        self.fuente_pequena = pygame.font.SysFont(
            "comicsansms", max(10, int(18 * escala)), bold=True
        )

    def _crear_rectangulos(self):
        """Calcula todas las filas de opciones como fracción del alto
        disponible, en vez de coordenadas fijas en píxeles, para que la
        pantalla siga siendo usable incluso en la resolución más chica
        (480x360) sin que las filas se salgan de la ventana."""
        centro = self.ancho // 2
        n_generales = 8  # resolucion, idioma, pantalla, dificultad, musica, efectos, escala_ui, reset
        n_controles = len(self.CONTROLES)

        self.titulo_y = max(30, int(self.alto * 0.09))

        ancho_boton_inferior = int(max(130, min(190, self.ancho * 0.22)))
        alto_boton_inferior = int(max(32, min(50, self.alto * 0.1)))
        margen_inferior = max(8, int(self.alto * 0.03))
        y_botones_inferiores = self.alto - alto_boton_inferior - margen_inferior

        y_inicio_filas = self.titulo_y + int(self.fuente_titulo.get_height() * 0.9)
        y_fin_filas = y_botones_inferiores - margen_inferior
        alto_disponible = max(1, y_fin_filas - y_inicio_filas)

        # +1.4 "unidades" de holgura: separación entre el bloque general y
        # el de controles, más espacio para el texto "press_key".
        unidades = n_generales + n_controles + 1.4
        alto_fila = max(20, min(38, alto_disponible / unidades))

        ancho_fila = int(max(240, min(460, self.ancho * 0.62)))
        alto_caja = max(16, int(alto_fila * 0.8))

        y = y_inicio_filas
        nombres_generales = (
            "boton_resolucion",
            "boton_idioma",
            "boton_pantalla",
            "boton_dificultad",
            "boton_musica",
            "boton_efectos",
            "boton_escala_ui",
            "boton_reset",
        )
        for nombre in nombres_generales:
            setattr(self, nombre, pygame.Rect(centro - ancho_fila // 2, int(y), ancho_fila, alto_caja))
            y += alto_fila

        self.press_key_y = int(y + alto_fila * 0.15)
        y += alto_fila * 1.4

        self.botones_controles = {}
        for nombre in self.CONTROLES:
            self.botones_controles[nombre] = pygame.Rect(
                centro - ancho_fila // 2, int(y), ancho_fila, max(14, int(alto_caja * 0.9))
            )
            y += alto_fila

        self.boton_volver = pygame.Rect(
            centro - ancho_boton_inferior - margen_inferior // 2,
            y_botones_inferiores,
            ancho_boton_inferior,
            alto_boton_inferior,
        )
        self.boton_guardar = pygame.Rect(
            centro + margen_inferior // 2,
            y_botones_inferiores,
            ancho_boton_inferior,
            alto_boton_inferior,
        )

    def actualizar_tamano(self, ancho, alto):
        self.ancho = ancho
        self.alto = alto
        self._crear_fuentes()
        self._crear_rectangulos()
        self._formas_abstractas = self._generar_formas_abstractas()

    def establecer_idioma(self, idioma):
        self.configuracion["idioma"] = idioma

    def _establecer_volumen_general(self, volumen):
        volumen = max(0.0, min(1.0, float(volumen)))
        self.configuracion["volumen_musica"] = volumen
        self.configuracion["volumen_efectos"] = volumen

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

    def _texto_centrado(self, superficie, contenido, fuente, centro, color=(255, 255, 255)):
        sombra = fuente.render(contenido, True, self.COLOR_TINTA)
        superficie.blit(sombra, sombra.get_rect(center=(centro[0] + 1, centro[1] + 1)))
        imagen = fuente.render(contenido, True, color)
        superficie.blit(imagen, imagen.get_rect(center=centro))

    def _puntos_garabateados(self, rect, fase, semilla, amplitud=1.3, segmentos=3):
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
        tam = 13 if hover else 8
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
        for _ in range(4):
            angulo = aleatorio.uniform(0, math.tau)
            distancia = aleatorio.uniform(rect.width * 0.4, rect.width * 0.6)
            x = rect.centerx + math.cos(angulo) * distancia
            y = rect.centery + math.sin(angulo) * distancia * 0.5
            radio = aleatorio.uniform(1.3, 3.0)
            pygame.draw.circle(superficie, color, (int(x), int(y)), radio)

    def _dibujar_boton_comic(self, superficie, rect, contenido, hover=False, activo=False, radio=14):
        """Botón estilo cómic-punk/fanzine: relleno plano con trama de
        puntos, contorno "dibujado a mano" con temblor, sombra dura de
        sticker despegado, y un aro cian pulsante cuando el boton esta
        "activo" (esperando una tecla)."""
        indice_color = (rect.x * 7 + rect.y * 13) % len(self.PALETA_BOTONES)
        color_base = self.PALETA_BOTONES[indice_color]
        if activo:
            color_base = self.COLOR_BOTON_ACTIVO
        elif hover:
            color_base = tuple(min(255, int(c * 1.12) + 8) for c in color_base)

        amplitud = 3.0 if activo else (2.6 if hover else 1.3)
        velocidad = 3.4 if activo else (2.4 if hover else 1.0)
        semilla = f"boton-{rect.x}-{rect.y}"
        puntos = self._puntos_garabateados(rect, self._tiempo * velocidad, semilla, amplitud=amplitud)

        elevacion = -3 if (hover or activo) else 0
        puntos = [(x, y + elevacion) for x, y in puntos]

        despl_sombra = (3, 4) if (hover or activo) else (6, 7)
        angulo_sombra = 2.0 if (hover or activo) else 3.5
        centro = (rect.centerx, rect.centery + elevacion)
        puntos_sombra = [self._rotar_punto(p, centro, angulo_sombra) for p in puntos]
        puntos_sombra = [(x + despl_sombra[0], y + despl_sombra[1]) for x, y in puntos_sombra]
        pygame.draw.polygon(superficie, self.COLOR_SOMBRA_STICKER, puntos_sombra)

        self._dibujar_relleno_halftone(superficie, puntos, color_base)

        if activo:
            # pulso cian tipo comic para indicar "esperando tecla"
            pulso = 0.5 + 0.5 * math.sin(self._tiempo * 8.0)
            grosor_pulso = max(2, int(rect.height * 0.1)) + int(pulso * 3)
            pygame.draw.polygon(superficie, self.COLOR_BOTON_ACTIVO, puntos, width=grosor_pulso)
        else:
            pygame.draw.polygon(superficie, self.COLOR_TINTA, puntos, width=max(2, int(rect.height * 0.09)))

        rect_dibujo = pygame.Rect(rect.left, rect.top + elevacion, rect.width, rect.height)
        if rect.width >= 90 and not activo:
            self._dibujar_esquina_pelada(superficie, rect_dibujo, hover)
        if hover and not activo:
            self._dibujar_salpicadura(superficie, rect_dibujo, self._tiempo)

        if contenido:
            self._texto_centrado(superficie, contenido, self.fuente, rect_dibujo.center)

        return rect_dibujo

    # ---------- dibujo principal ----------

    def _nombre_tecla(self, nombre):
        return pygame.key.name(self.configuracion["controles"][nombre]).upper()

    def _restaurar_por_defecto(self):
        self.configuracion["resolucion"] = self.DEFAULTS["resolucion"]
        self.configuracion["pantalla_completa"] = self.DEFAULTS["pantalla_completa"]
        self.configuracion["idioma"] = self.DEFAULTS["idioma"]
        self.configuracion["volumen_musica"] = self.DEFAULTS["volumen_musica"]
        self._establecer_volumen_general(self.DEFAULTS["volumen_musica"])
        self.configuracion["escala_ui"] = self.DEFAULTS["escala_ui"]
        self.configuracion["controles"] = self.DEFAULTS["controles"].copy()
        self._crear_fuentes()
        self._crear_rectangulos()

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
            (self.ancho // 2, self.titulo_y + bamboleo),
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

        hover = self.boton_dificultad.collidepoint(posicion_raton)
        rect_dibujo = self._dibujar_boton_comic(superficie, self.boton_dificultad, "", hover)
        self._texto_centrado(
            superficie,
            f"{texto(idioma, 'difficulty')}: {texto(idioma, 'progressive_by_level')}",
            self.fuente_pequena,
            rect_dibujo.center,
        )

        volumen_musica = int(round(self.configuracion.get("volumen_musica", 0.8) * 100))
        hover = self.boton_musica.collidepoint(posicion_raton)
        rect_dibujo = self._dibujar_boton_comic(superficie, self.boton_musica, "", hover)
        self._texto_centrado(
            superficie,
            f"{texto(idioma, 'music')}: {volumen_musica}%",
            self.fuente_pequena,
            rect_dibujo.center,
        )

        volumen_efectos = int(round(self.configuracion.get("volumen_efectos", 0.85) * 100))
        hover = self.boton_efectos.collidepoint(posicion_raton)
        rect_dibujo = self._dibujar_boton_comic(superficie, self.boton_efectos, "", hover)
        self._texto_centrado(
            superficie,
            f"{texto(idioma, 'effects')}: {volumen_efectos}%",
            self.fuente_pequena,
            rect_dibujo.center,
        )

        escala_ui_actual = int(round(self.configuracion.get("escala_ui", 1.0) * 100))
        hover = self.boton_escala_ui.collidepoint(posicion_raton)
        rect_dibujo = self._dibujar_boton_comic(superficie, self.boton_escala_ui, "", hover)
        self._texto_centrado(
            superficie,
            f"{texto(idioma, 'ui_scale')}: {escala_ui_actual}%",
            self.fuente_pequena,
            rect_dibujo.center,
        )

        hover = self.boton_reset.collidepoint(posicion_raton)
        rect_dibujo = self._dibujar_boton_comic(superficie, self.boton_reset, "", hover)
        self._texto_centrado(
            superficie,
            texto(idioma, "reset_defaults"),
            self.fuente_pequena,
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
                (self.ancho // 2, self.press_key_y),
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
        elif self.boton_musica.collidepoint(evento.pos):
            valores = (0.0, 0.25, 0.5, 0.75, 1.0)
            actual = self.configuracion.get("volumen_musica", 0.8)
            indice = valores.index(actual) if actual in valores else 3
            self._establecer_volumen_general(valores[(indice + 1) % len(valores)])
        elif self.boton_efectos.collidepoint(evento.pos):
            valores = (0.0, 0.25, 0.5, 0.75, 1.0)
            actual = self.configuracion.get("volumen_efectos", 0.85)
            indice = valores.index(actual) if actual in valores else 3
            self._establecer_volumen_general(valores[(indice + 1) % len(valores)])
        elif self.boton_escala_ui.collidepoint(evento.pos):
            actual = self.configuracion.get("escala_ui", 1.0)
            if actual in self.ESCALAS_UI:
                indice = self.ESCALAS_UI.index(actual)
            else:
                # valor guardado no coincide exactamente (p. ej. config vieja):
                # se ubica en el escalón cicleable mas cercano.
                indice = min(range(len(self.ESCALAS_UI)), key=lambda i: abs(self.ESCALAS_UI[i] - actual)) - 1
            self.configuracion["escala_ui"] = self.ESCALAS_UI[(indice + 1) % len(self.ESCALAS_UI)]
            self._crear_fuentes()
            self._crear_rectangulos()
        elif self.boton_reset.collidepoint(evento.pos):
            self._restaurar_por_defecto()
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


def normalizar_configuracion(configuracion):
    """Combina los valores guardados con los valores por defecto del juego."""
    base = {
        "resoluciones": MenuOpciones.RESOLUCIONES,
        "resolucion": 0,
        "pantalla_completa": False,
        "idioma": "en",
        "volumen_musica": 0.8,
        "volumen_efectos": 0.8,
        "escala_ui": 1.0,
        "controles": MenuOpciones.DEFAULTS["controles"].copy(),
    }
    if not isinstance(configuracion, dict):
        return base

    for clave, valor in base.items():
        if clave == "controles":
            if isinstance(configuracion.get("controles"), dict):
                base["controles"] = MenuOpciones.DEFAULTS["controles"].copy()
                base["controles"].update(configuracion["controles"])
            continue
        if clave in configuracion:
            base[clave] = configuracion[clave]

    if "resoluciones" in configuracion and isinstance(configuracion["resoluciones"], (list, tuple)):
        base["resoluciones"] = tuple(configuracion["resoluciones"])

    return base


def _ruta_configuracion(ruta=None):
    if ruta is not None:
        return ruta
    return os.path.join(os.path.dirname(__file__), "configuracion_guardada.json")


def cargar_configuracion(ruta=None):
    """Lee la configuración persistida del juego y devuelve una copia normalizada."""
    ruta_final = _ruta_configuracion(ruta)
    if not os.path.exists(ruta_final):
        return normalizar_configuracion({})

    try:
        with open(ruta_final, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except (OSError, ValueError, TypeError):
        return normalizar_configuracion({})

    return normalizar_configuracion(datos)


def guardar_configuracion(configuracion, ruta=None):
    """Guarda la configuración actual del juego para reutilizarla la próxima sesión."""
    ruta_final = _ruta_configuracion(ruta)
    directorio = os.path.dirname(ruta_final)
    if directorio:
        os.makedirs(directorio, exist_ok=True)

    datos = normalizar_configuracion(configuracion)
    datos["resoluciones"] = list(datos["resoluciones"])
    datos["controles"] = {nombre: int(tecla) for nombre, tecla in datos["controles"].items()}

    with open(ruta_final, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, ensure_ascii=False, indent=2)

    return ruta_final