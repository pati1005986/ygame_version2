"""Utilidades de presentación: escalado del lienzo y viñeta de peligro."""

import numpy as np
import pygame


def crear_vineta_peligro(ancho, alto):
    """Prepara UNA VEZ (no en cada fotograma) una superficie con una viñeta
    roja radial: transparente en el centro, más opaca hacia los bordes.

    Se usa como aviso de que un enemigo está muy cerca: cada fotograma solo
    hace falta ajustar su transparencia global (``set_alpha``) según
    ``alerta_enemigos`` y pegarla (un solo ``blit``), así que es barata de
    mantener en el bucle principal aunque el cálculo con numpy que arma el
    degradado -relativamente caro- se hace solo aquí, al iniciar el juego.
    """
    y, x = np.mgrid[0:alto, 0:ancho]
    centro_x, centro_y = ancho / 2, alto / 2
    distancia = np.sqrt(((x - centro_x) / centro_x) ** 2 + ((y - centro_y) / centro_y) ** 2)
    alpha = np.clip((distancia - 0.55) / (1.3 - 0.55), 0.0, 1.0) ** 1.6

    rgba = np.zeros((alto, ancho, 4), dtype=np.uint8)
    rgba[:, :, 0] = 175  # tinte rojo de advertencia
    rgba[:, :, 1] = 15
    rgba[:, :, 2] = 15
    rgba[:, :, 3] = (alpha * 235).astype(np.uint8)
    superficie = pygame.image.frombuffer(rgba.tobytes(), (ancho, alto), "RGBA")
    return superficie.convert_alpha()


class Presentador:
    """Dueño de la ventana y del lienzo lógico donde se dibuja todo.

    El juego dibuja siempre en ``lienzo`` (tamaño lógico fijo) y
    ``presentar`` lo escala a la resolución real de la ventana.
    """

    def __init__(self, ancho, alto, resolucion, flags=0):
        self.screen = pygame.display.set_mode(resolucion, flags)
        self.lienzo = pygame.Surface((ancho, alto))
        self._escalada = None

    def presentar(self):
        tamano_pantalla = self.screen.get_size()
        if tamano_pantalla == self.lienzo.get_size():
            self.screen.blit(self.lienzo, (0, 0))
            return

        if self._escalada is None or self._escalada.get_size() != tamano_pantalla:
            self._escalada = pygame.Surface(tamano_pantalla).convert()
        # ``scale`` es notablemente más rápido que ``smoothscale`` y para el
        # estilo pixel-art/caricaturesco del juego la diferencia visual es
        # mínima. Esta operación corre 60 veces por segundo.
        pygame.transform.scale(self.lienzo, tamano_pantalla, self._escalada)
        self.screen.blit(self._escalada, (0, 0))

    def posicion_raton_logica(self):
        """Posición del ratón convertida a coordenadas del lienzo lógico."""
        x, y = pygame.mouse.get_pos()
        ancho, alto = self.lienzo.get_size()
        return (
            int(x * ancho / self.screen.get_width()),
            int(y * alto / self.screen.get_height()),
        )