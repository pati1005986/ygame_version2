import colorsys
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
        sombra = fuente.render(contenido, True, self.COLOR_BOTON_BORDE)
        superficie.blit(sombra, sombra.get_rect(center=(centro[0] + 1, centro[1] + 1)))
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
        num_destellos = 4 if hover else 2
        if columnas >= 5 and filas >= 5:
            for _ in range(num_destellos):
                col = aleatorio_destellos.randint(2, columnas - 3)
                fila = aleatorio_destellos.randint(2, filas - 3)
                lienzo_bajo.set_at((col, fila), (255, 255, 255))

        return pygame.transform.scale(lienzo_bajo, (ancho, alto))

    def _dibujar_boton_comic(self, superficie, rect, contenido, hover=False, activo=False, radio=14):
        """Botón arcoíris pixelado y caricaturesco: relleno tipo 8-bit con
        bandas de color que se desplazan y contorno grueso estilo comic."""
        desplazamiento_sombra = max(2, int(rect.height * 0.2)) if not hover else max(1, int(rect.height * 0.1))
        rect_sombra = rect.move(desplazamiento_sombra, desplazamiento_sombra)
        pygame.draw.rect(superficie, self.COLOR_BOTON_SOMBRA, rect_sombra)

        rect_dibujo = rect.move(-3 if hover else 0, -3 if hover else 0)

        velocidad_desfile = 1.4 if hover else 0.7
        semilla_destellos = f"boton-{rect.x}-{rect.y}-{int(self._tiempo * (10 if hover else 3))}"
        textura = self._generar_textura_boton_pixelada(
            rect_dibujo.width,
            rect_dibujo.height,
            self._tiempo * velocidad_desfile,
            hover,
            semilla_destellos,
        )
        superficie.blit(textura, rect_dibujo.topleft)

        if activo:
            # pulso cian tipo comic para indicar "esperando tecla"
            pulso = 0.5 + 0.5 * math.sin(self._tiempo * 8.0)
            grosor_pulso = max(2, int(rect_dibujo.height * 0.12)) + int(pulso * 3)
            pygame.draw.rect(superficie, (90, 230, 200), rect_dibujo, width=grosor_pulso)
        else:
            pygame.draw.rect(
                superficie, self.COLOR_BOTON_BORDE, rect_dibujo, width=max(2, int(rect_dibujo.height * 0.12))
            )

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