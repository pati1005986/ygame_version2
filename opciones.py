import json
import math
import os
import random

import pygame

from idioma import alternar_idioma, texto
from ui_pixel import FormasPixel, UIPixel


class MenuOpciones:
    """Pantalla independiente para configurar el juego, con estilo
    caricaturesco y fondo de arte abstracto.

    ``configuracion`` se modifica en el sitio para que el bucle principal pueda
    reutilizarla al volver al menu.
    """

    # Las nuevas resoluciones van al final para que los indices guardados en
    # configuracion_guardada.json sigan apuntando a la misma resolucion.
    # Todas son 4:3, igual que el lienzo logico de 800x600.
    RESOLUCIONES = (
        (800, 600),
        (640, 480),
        (480, 360),
        (1024, 768),
        (1280, 960),
        (1600, 1200),
    )
    # Niveles de calidad grafica (indice guardado en "calidad_graficos").
    CALIDADES_GRAFICAS = ("low", "medium", "high")
    CONTROLES = ("left", "right", "jump", "down", "dash")
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
        "calidad_graficos": 2,
        "idioma": "en",
        "volumen_musica": 0.8,
        "volumen_efectos": 0.8,
        "escala_ui": 1.0,
        "controles": {
            "left": pygame.K_a,
            "right": pygame.K_d,
            "jump": pygame.K_SPACE,
            "down": pygame.K_s,
            "dash": pygame.K_LSHIFT,
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
        validas = self.resoluciones_disponibles()
        if self.configuracion["resolucion"] not in validas:
            self.configuracion["resolucion"] = validas[0]
        self.tecla_esperada = None
        self._tiempo = 0.0
        self.ui = UIPixel()
        self.ui_texto = UIPixel(px=1, antialias=True)
        self._contador_boton = 0
        self._ctx_texto = (None, 10)
        self._crear_fuentes()
        self._crear_rectangulos()
        self._formas_abstractas = self._generar_formas_abstractas()

    @classmethod
    def resoluciones_disponibles(cls):
        """Indices de las resoluciones que caben en el monitor actual.

        Tambien ofrece la resolucion actual del escritorio si no esta en la
        lista fija.
        Siempre devuelve al menos la resolucion base (indice 0).
        """
        resoluciones = cls.resoluciones_configuracion()
        try:
            ancho_max, alto_max = pygame.display.get_desktop_sizes()[0]
        except (pygame.error, AttributeError, IndexError):
            return list(range(len(resoluciones)))
        validas = [
            i
            for i, (ancho, alto) in enumerate(resoluciones)
            if ancho <= ancho_max and alto <= alto_max
        ]
        return validas or [0]

    @classmethod
    def resoluciones_configuracion(cls):
        """Devuelve los tamaños fijos y, si hace falta, el del escritorio."""
        resoluciones = list(cls.RESOLUCIONES)
        try:
            escritorio = pygame.display.get_desktop_sizes()[0]
        except (pygame.error, AttributeError, IndexError):
            return resoluciones
        if escritorio not in resoluciones:
            resoluciones.append(escritorio)
        return resoluciones

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

    # Tamaño de pixel base de esta pantalla: los botones son bajos, así que
    # usa una rejilla más fina (2) que el menú principal (3).
    PIXEL_BASE_UI = 2

    def _crear_fuentes(self):
        """Calcula tamaños físicos de texto a partir de la escala visual."""
        self.ui.establecer_px(UIPixel.px_para(self._escala(), self.PIXEL_BASE_UI))
        self.fuente_titulo = 18 * self.ui.px
        self.fuente = 9 * self.ui.px
        self.fuente_pequena = 8 * self.ui.px

    def _crear_rectangulos(self):
        """Calcula todas las filas de opciones como fracción del alto
        disponible, en vez de coordenadas fijas en píxeles, para que la
        pantalla siga siendo usable incluso en la resolución más chica
        (480x360) sin que las filas se salgan de la ventana."""
        centro = self.ancho // 2
        n_generales = 9  # resolucion, idioma, pantalla, graficos, dificultad, musica, efectos, escala_ui, reset
        n_controles = len(self.CONTROLES)

        self.titulo_y = max(30, int(self.alto * 0.09))

        ancho_boton_inferior = int(max(130, min(190, self.ancho * 0.22)))
        alto_boton_inferior = int(max(32, min(50, self.alto * 0.1)))
        margen_inferior = max(8, int(self.alto * 0.03))
        y_botones_inferiores = self.alto - alto_boton_inferior - margen_inferior

        y_inicio_filas = self.titulo_y + int(self.fuente_titulo * 1.25 * 0.9)
        y_fin_filas = y_botones_inferiores - margen_inferior
        alto_disponible = max(1, y_fin_filas - y_inicio_filas)

        # +1.4 "unidades" de holgura: separación entre el bloque general y
        # el de controles, más espacio para el texto "press_key".
        unidades = n_generales + n_controles + 1.4
        alto_fila = max(14, min(38, alto_disponible / unidades))

        ancho_fila = int(max(240, min(460, self.ancho * 0.62)))
        alto_caja = max(16, int(alto_fila * 0.8))

        y = y_inicio_filas
        nombres_generales = (
            "boton_resolucion",
            "boton_idioma",
            "boton_pantalla",
            "boton_graficos",
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
        return FormasPixel(
            self.ui, self.ancho, self.alto, self.COLORES_ABSTRACTOS,
            f"opciones-{self.ancho}x{self.alto}", cantidad=14,
        )

    def _dibujar_formas_abstractas(self, superficie):
        self._formas_abstractas.dibujar(superficie, self._tiempo)

    # ---------- utilidades de dibujo "caricaturesco" ----------

    def _texto_contorno(self, superficie, contenido, tam, centro, color_relleno, color_contorno=None, grosor=None):
        """Dibuja texto suavizado con contorno; ``tam`` se expresa en pixeles."""
        self.ui_texto.texto(superficie, contenido.upper(), centro, color_relleno, tam)

    def _texto_centrado(self, superficie, contenido, tam, centro, color=(255, 255, 255)):
        """Texto dentro del último botón dibujado: se encoge si no cabe."""
        ancho_max, tam_max = self._ctx_texto
        self.ui_texto.texto(
            superficie, contenido.upper(), centro, color, min(tam, tam_max),
            ancho_max=ancho_max,
        )

    def _dibujar_boton_comic(self, superficie, rect, contenido, hover=False, activo=False, radio=14):
        """Botón pixel art (ver ``UIPixel.boton``). El color sale del orden de
        dibujo, así que es estable entre fotogramas. Devuelve el rect del
        cuerpo para centrar el texto encima."""
        indice = self._contador_boton
        self._contador_boton += 1
        cuerpo = self.ui.boton(
            superficie, rect, self.ui.color(indice), "",
            hover=hover, activo=activo, tiempo=self._tiempo, tam=self.fuente,
        )
        self._ctx_texto = (
            cuerpo.w - 4 * self.ui.px,
            self.ui_texto.tam_para_alto(cuerpo.h, 99),
        )
        if contenido:
            self._texto_centrado(
                superficie, contenido, self.fuente, cuerpo.center
            )
        return cuerpo

    # ---------- dibujo principal ----------

    def _texto_graficos(self, idioma, clave):
        return texto(idioma, clave)

    def _nombre_tecla(self, nombre):
        return pygame.key.name(self.configuracion["controles"][nombre]).upper()

    def _restaurar_por_defecto(self):
        self.configuracion["resolucion"] = self.DEFAULTS["resolucion"]
        self.configuracion["pantalla_completa"] = self.DEFAULTS["pantalla_completa"]
        self.configuracion["calidad_graficos"] = self.DEFAULTS["calidad_graficos"]
        self.configuracion["idioma"] = self.DEFAULTS["idioma"]
        self.configuracion["volumen_musica"] = self.DEFAULTS["volumen_musica"]
        self._establecer_volumen_general(self.DEFAULTS["volumen_musica"])
        self.configuracion["escala_ui"] = self.DEFAULTS["escala_ui"]
        self.configuracion["controles"] = self.DEFAULTS["controles"].copy()
        self._crear_fuentes()
        self._crear_rectangulos()

    def dibujar(self, superficie, mouse_pos=None, dt=1 / 60):
        self._tiempo += dt
        self._contador_boton = 0
        posicion_raton = mouse_pos if mouse_pos is not None else pygame.mouse.get_pos()

        superficie.fill(self.COLOR_FONDO)
        self._dibujar_formas_abstractas(superficie)

        # veladura para que el texto siga siendo legible sobre el arte abstracto
        veladura = pygame.Surface((self.ancho, self.alto), pygame.SRCALPHA)
        veladura.fill((15, 8, 30, 95))
        superficie.blit(veladura, (0, 0))

        idioma = self.configuracion["idioma"]
        self.ui_texto.titulo(
            superficie,
            texto(idioma, "options").upper(),
            (self.ancho // 2, self.titulo_y),
            self.COLOR_TITULO,
            tam=self.fuente_titulo,
            tiempo=self._tiempo,
            ancho_max=self.ancho - 24,
        )

        indice_resolucion = self.configuracion["resolucion"]
        resolucion = self.configuracion["resoluciones"][indice_resolucion]
        etiqueta_resolucion = (
            f"{texto(idioma, 'max_resolution')}: "
            if indice_resolucion == len(self.RESOLUCIONES)
            else ""
        )
        hover = self.boton_resolucion.collidepoint(posicion_raton)
        rect_dibujo = self._dibujar_boton_comic(superficie, self.boton_resolucion, "", hover)
        self._texto_centrado(
            superficie,
            f"{texto(idioma, 'resolution')}: {etiqueta_resolucion}"
            f"{resolucion[0]} X {resolucion[1]}",
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

        calidad = self.configuracion.get("calidad_graficos", 2)
        calidad = max(0, min(len(self.CALIDADES_GRAFICAS) - 1, calidad))
        hover = self.boton_graficos.collidepoint(posicion_raton)
        rect_dibujo = self._dibujar_boton_comic(superficie, self.boton_graficos, "", hover)
        self._texto_centrado(
            superficie,
            f"{self._texto_graficos(idioma, 'graphics')}: "
            f"{self._texto_graficos(idioma, self.CALIDADES_GRAFICAS[calidad])}",
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
            "dash": "dash",
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

        self.ui.scanlines(superficie)

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
            validas = self.resoluciones_disponibles()
            siguientes = [i for i in validas if i > self.configuracion["resolucion"]]
            self.configuracion["resolucion"] = siguientes[0] if siguientes else validas[0]
        elif self.boton_idioma.collidepoint(evento.pos):
            self.configuracion["idioma"] = alternar_idioma(self.configuracion["idioma"])
        elif self.boton_pantalla.collidepoint(evento.pos):
            self.configuracion["pantalla_completa"] = not self.configuracion.get("pantalla_completa", False)
        elif self.boton_graficos.collidepoint(evento.pos):
            self.configuracion["calidad_graficos"] = (
                self.configuracion.get("calidad_graficos", 2) + 1
            ) % len(self.CALIDADES_GRAFICAS)
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
        "calidad_graficos": 2,
        "idioma": "en",
        "volumen_musica": 0.8,
        "volumen_efectos": 0.8,
        "escala_ui": 1.0,
        "juego_completado": False,
        "nivel_guardado": 1,
        "mejor_puntaje_infinito": 0,
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

    # La lista de resoluciones siempre sale del codigo, nunca del JSON
    # guardado: asi un archivo viejo no oculta las resoluciones nuevas.
    base["resoluciones"] = MenuOpciones.RESOLUCIONES
    indice_res = base["resolucion"]
    if (
        isinstance(indice_res, bool)
        or not isinstance(indice_res, int)
        or not 0 <= indice_res <= len(MenuOpciones.RESOLUCIONES)
    ):
        base["resolucion"] = 0

    calidad = base["calidad_graficos"]
    if (
        isinstance(calidad, bool)
        or not isinstance(calidad, int)
        or not 0 <= calidad < len(MenuOpciones.CALIDADES_GRAFICAS)
    ):
        base["calidad_graficos"] = 2

    nivel_guardado = base["nivel_guardado"]
    if isinstance(nivel_guardado, bool) or not isinstance(nivel_guardado, int) or nivel_guardado < 1:
        base["nivel_guardado"] = 1

    mejor_puntaje = base["mejor_puntaje_infinito"]
    if (
        isinstance(mejor_puntaje, bool)
        or not isinstance(mejor_puntaje, int)
        or mejor_puntaje < 0
    ):
        base["mejor_puntaje_infinito"] = 0

    if not isinstance(base["juego_completado"], bool):
        base["juego_completado"] = False

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