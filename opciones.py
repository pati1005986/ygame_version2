import pygame


class MenuOpciones:
    """Pantalla independiente para configurar el juego.

    La interfaz se mantiene en ingles porque es el unico idioma disponible.
    ``configuracion`` se modifica en el sitio para que el bucle principal pueda
    reutilizarla al volver al menu.
    """

    RESOLUCIONES = ((800, 600), (640, 480), (480, 360))
    CONTROLES = (
        ("left", "MOVE LEFT"),
        ("right", "MOVE RIGHT"),
        ("jump", "JUMP"),
        ("down", "CROUCH"),
    )

    def __init__(self, ancho, alto, configuracion):
        self.ancho = ancho
        self.alto = alto
        self.configuracion = configuracion
        self.fuente_titulo = pygame.font.SysFont("arial", 38, bold=True)
        self.fuente = pygame.font.SysFont("arial", 22)
        self.fuente_pequena = pygame.font.SysFont("arial", 18)
        self.tecla_esperada = None
        self._crear_rectangulos()

    def _crear_rectangulos(self):
        centro = self.ancho // 2
        self.boton_resolucion = pygame.Rect(centro - 190, 130, 380, 48)
        self.boton_idioma = pygame.Rect(centro - 190, 194, 380, 48)
        self.boton_volver = pygame.Rect(centro - 190, self.alto - 72, 180, 48)
        self.boton_guardar = pygame.Rect(centro + 10, self.alto - 72, 180, 48)
        inicio_controles = 285
        self.botones_controles = {
            nombre: pygame.Rect(centro - 190, inicio_controles + indice * 48, 380, 38)
            for indice, (nombre, _) in enumerate(self.CONTROLES)
        }

    def actualizar_tamano(self, ancho, alto):
        self.ancho = ancho
        self.alto = alto
        self._crear_rectangulos()

    def _texto_centrado(self, superficie, texto, fuente, centro, color=(235, 240, 245)):
        imagen = fuente.render(texto, True, color)
        superficie.blit(imagen, imagen.get_rect(center=centro))

    def _nombre_tecla(self, nombre):
        return pygame.key.name(self.configuracion["controles"][nombre]).upper()

    def dibujar(self, superficie):
        superficie.fill((10, 12, 18))
        pygame.draw.rect(superficie, (18, 27, 38), (0, 0, self.ancho, self.alto))
        self._texto_centrado(superficie, "OPTIONS", self.fuente_titulo, (self.ancho // 2, 55))

        resolucion = self.configuracion["resoluciones"][self.configuracion["resolucion"]]
        self._texto_centrado(
            superficie,
            f"RESOLUTION: {resolucion[0]} X {resolucion[1]}",
            self.fuente,
            self.boton_resolucion.center,
        )
        self._texto_centrado(
            superficie,
            "LANGUAGE: ENGLISH",
            self.fuente,
            self.boton_idioma.center,
        )

        for nombre, texto in self.CONTROLES:
            rect = self.botones_controles[nombre]
            etiqueta = f"{texto}: {self._nombre_tecla(nombre)}"
            color = (90, 220, 255) if self.tecla_esperada == nombre else (235, 240, 245)
            pygame.draw.rect(superficie, (30, 42, 55), rect)
            pygame.draw.rect(superficie, color, rect, 2)
            self._texto_centrado(superficie, etiqueta, self.fuente_pequena, rect.center, color)

        if self.tecla_esperada:
            self._texto_centrado(
                superficie,
                "PRESS A KEY... ESC CANCELS",
                self.fuente_pequena,
                (self.ancho // 2, 265),
                (255, 210, 120),
            )

        for rect, texto in ((self.boton_volver, "BACK"), (self.boton_guardar, "APPLY")):
            pygame.draw.rect(superficie, (24, 34, 45), rect)
            pygame.draw.rect(superficie, (90, 220, 255), rect, 2)
            self._texto_centrado(superficie, texto, self.fuente, rect.center)

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
            self.configuracion["idioma"] = "en"
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
