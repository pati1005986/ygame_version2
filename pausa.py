import pygame

from idioma import texto
from ui_pixel import FormasPixel, UIPixel


class MenuPausa:
    """Menú de pausa con estética retro pixel art, dibujado sobre el lienzo
    lógico del juego. Usa los componentes de ``ui_pixel``."""

    # Resolucion de referencia sobre la que se disenaron los tamanos
    # originales; el factor de escala se calcula relativo a esto.
    ANCHO_REFERENCIA = 800
    ALTO_REFERENCIA = 600
    ESCALA_MIN = 0.55
    ESCALA_MAX = 1.6

    COLOR_FONDO_OVERLAY = (10, 12, 26, 190)
    COLOR_TITULO = (255, 228, 102)

    # Formas de fondo (RGBA)
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
        self.ui = UIPixel()
        self._reconstruir()

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

    def _reconstruir(self):
        self.ui.establecer_px(UIPixel.px_para(self._escala()))
        self._crear_rectangulos()
        self._formas = FormasPixel(
            self.ui, self.ancho, self.alto, self.COLORES_ABSTRACTOS,
            f"pausa-{self.ancho}x{self.alto}", cantidad=12,
        )
        self._capa_overlay = None

    def _crear_rectangulos(self):
        centro = self.ancho // 2

        ancho_boton = int(max(190, min(340, self.ancho * 0.4)))
        alto_boton = int(max(34, min(56, self.alto * 0.085)))
        espacio = max(6, int(alto_boton * 0.22))
        bloque_alto = alto_boton * 4 + espacio * 3

        titulo_y = max(45, int(self.alto * 0.16))
        margen_bajo_titulo = titulo_y + int(alto_boton * 0.75)
        y_maximo = self.alto - bloque_alto - int(self.alto * 0.03)
        y_inicio = min(
            max(margen_bajo_titulo, int(self.alto * 0.32)),
            max(margen_bajo_titulo, y_maximo),
        )

        panel_ancho = max(ancho_boton + 86, int(self.ancho * 0.52))
        panel_alto = bloque_alto + 74
        panel_top = max(30, y_inicio - 48)
        self.panel_rect = pygame.Rect(centro - panel_ancho // 2, panel_top, panel_ancho, panel_alto)

        self.titulo_y = titulo_y
        x = centro - ancho_boton // 2
        paso = alto_boton + espacio
        self.boton_continuar = pygame.Rect(x, y_inicio, ancho_boton, alto_boton)
        self.boton_opciones = pygame.Rect(x, y_inicio + paso, ancho_boton, alto_boton)
        self.boton_menu = pygame.Rect(x, y_inicio + paso * 2, ancho_boton, alto_boton)
        self.boton_salir = pygame.Rect(x, y_inicio + paso * 3, ancho_boton, alto_boton)

    def actualizar_tamano(self, ancho, alto):
        self.ancho = ancho
        self.alto = alto
        self._reconstruir()

    def establecer_idioma(self, idioma):
        self.idioma = idioma

    def establecer_escala_ui(self, escala_ui):
        self.escala_ui = escala_ui
        self._reconstruir()

    # ---------- dibujo ----------

    def _dibujar_titulo_pausa(self, superficie):
        self.ui.barra(superficie, self.ancho // 2, self.titulo_y + 34, 260)
        self.ui.titulo(
            superficie,
            texto(self.idioma, "pause").upper(),
            (self.ancho // 2, self.titulo_y),
            self.COLOR_TITULO,
            tam=18,
            tiempo=self._tiempo,
            ancho_max=self.panel_rect.width - 24,
        )

    def dibujar(self, superficie, mouse_pos=None, dt=1 / 60):
        self._tiempo += dt

        self._formas.dibujar(superficie, self._tiempo)

        if self._capa_overlay is None:
            self._capa_overlay = pygame.Surface((self.ancho, self.alto), pygame.SRCALPHA)
            self._capa_overlay.fill(self.COLOR_FONDO_OVERLAY)
        superficie.blit(self._capa_overlay, (0, 0))

        self.ui.panel(superficie, self.panel_rect)
        self._dibujar_titulo_pausa(superficie)

        botones = (
            (self.boton_continuar, "continue"),
            (self.boton_opciones, "options"),
            (self.boton_menu, "main_menu"),
            (self.boton_salir, "exit"),
        )
        posicion_raton = mouse_pos if mouse_pos is not None else pygame.mouse.get_pos()
        for indice, (rect, clave) in enumerate(botones):
            self.ui.boton(
                superficie,
                rect,
                self.ui.color(indice),
                texto(self.idioma, clave).upper(),
                hover=rect.collidepoint(posicion_raton),
                tiempo=self._tiempo,
                tam=10,
            )

        self.ui.scanlines(superficie)

    def manejar_evento(self, evento):
        if evento.type == pygame.KEYDOWN and evento.key == pygame.K_ESCAPE:
            return "continuar"
        if evento.type != pygame.MOUSEBUTTONDOWN or evento.button != 1:
            return None
        if self.boton_continuar.collidepoint(evento.pos):
            return "continuar"
        if self.boton_opciones.collidepoint(evento.pos):
            return "opciones"
        if self.boton_menu.collidepoint(evento.pos):
            return "menu"  # Retorna el estado para volver al menú principal
        if self.boton_salir.collidepoint(evento.pos):
            return "salir"
        return None