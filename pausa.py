import pygame

from idioma import texto


class MenuPausa:
    """Menu de pausa dibujado sobre el lienzo logico del juego."""

    def __init__(self, ancho, alto, idioma="en"):
        self.ancho = ancho
        self.alto = alto
        self.idioma = idioma
        self.fuente_titulo = pygame.font.SysFont("arial", 48, bold=True)
        self.fuente_boton = pygame.font.SysFont("arial", 22, bold=True)
        self._crear_rectangulos()

    def _crear_rectangulos(self):
        centro = self.ancho // 2
        self.boton_continuar = pygame.Rect(centro - 150, 245, 300, 50)
        self.boton_opciones = pygame.Rect(centro - 150, 310, 300, 50)
        self.boton_salir = pygame.Rect(centro - 150, 375, 300, 50)

    def actualizar_tamano(self, ancho, alto):
        self.ancho = ancho
        self.alto = alto
        self._crear_rectangulos()

    def establecer_idioma(self, idioma):
        self.idioma = idioma

    def _texto_centrado(self, superficie, contenido, fuente, centro, color):
        imagen = fuente.render(contenido, True, color)
        superficie.blit(imagen, imagen.get_rect(center=centro))

    def dibujar(self, superficie, mouse_pos=None):
        capa = pygame.Surface((self.ancho, self.alto), pygame.SRCALPHA)
        capa.fill((0, 0, 0, 175))
        superficie.blit(capa, (0, 0))
        self._texto_centrado(
            superficie,
            texto(self.idioma, "pause"),
            self.fuente_titulo,
            (self.ancho // 2, 145),
            (235, 240, 245),
        )

        botones = (
            (self.boton_continuar, "continue"),
            (self.boton_opciones, "options"),
            (self.boton_salir, "exit"),
        )
        posicion_raton = mouse_pos if mouse_pos is not None else pygame.mouse.get_pos()
        for rect, clave in botones:
            hover = rect.collidepoint(posicion_raton)
            color = (45, 70, 86) if hover else (24, 34, 45)
            pygame.draw.rect(superficie, color, rect)
            pygame.draw.rect(superficie, (90, 220, 255), rect, 2)
            self._texto_centrado(
                superficie,
                texto(self.idioma, clave),
                self.fuente_boton,
                rect.center,
                (255, 255, 255),
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
