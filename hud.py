"""Interfaz en pantalla: fuentes, aviso inicial y HUD con textos cacheados.

Los textos se vuelven a renderizar solo cuando cambia el dato que muestran
(nivel, idioma, combo...), no en cada fotograma.
"""

import math
import random

import pygame

from idioma import texto


def _fuente_negrita(tamano):
    fuente = pygame.font.Font(None, tamano)
    fuente.set_bold(True)
    return fuente


class Fuentes:
    """Todas las fuentes del juego, creadas una sola vez."""

    def __init__(self):
        self.base = pygame.font.Font(None, 36)
        self.titulo_advertencia = _fuente_negrita(46)
        self.advertencia = pygame.font.Font(None, 26)
        self.prompt_advertencia = pygame.font.Font(None, 22)
        self.combo = _fuente_negrita(26)
        self.resumen = _fuente_negrita(32)
        self.boton_creditos = pygame.font.SysFont("comicsansms", 14, bold=True)


def crear_fuente_boton(texto_boton, ancho_maximo):
    """Devuelve ``(tamaño, fuente)`` reduciendo el tamaño hasta que el texto quepa."""
    tamano = 36
    fuente = _fuente_negrita(tamano)
    while tamano > 16 and fuente.size(texto_boton)[0] > ancho_maximo:
        tamano -= 1
        fuente = _fuente_negrita(tamano)
    return tamano, fuente


class PantallaAdvertencia:
    """Aviso de epilepsia que se muestra al arrancar."""

    def __init__(self, fuentes, ancho):
        self.fuentes = fuentes
        self.centro_x = ancho // 2
        self._idioma = None
        self._textos = ()

    def _renderizar(self, idioma):
        f, cx = self.fuentes, self.centro_x
        blanco, gris = (245, 245, 245), (180, 180, 190)
        self._idioma = idioma
        self._textos = (
            (f.titulo_advertencia.render(texto(idioma, "epilepsy_warning_title"), True, (255, 210, 80)), (cx, 190)),
            (f.advertencia.render(texto(idioma, "epilepsy_warning_line_1"), True, blanco), (cx, 275)),
            (f.advertencia.render(texto(idioma, "epilepsy_warning_line_2"), True, blanco), (cx, 315)),
            (f.prompt_advertencia.render(texto(idioma, "epilepsy_warning_continue"), True, gris), (cx, 430)),
        )

    def dibujar(self, lienzo, idioma):
        lienzo.fill((8, 8, 12))
        if idioma != self._idioma:
            self._renderizar(idioma)
        for superficie, centro in self._textos:
            lienzo.blit(superficie, superficie.get_rect(center=centro))


class HUD:
    """Nivel, puntaje, combo/dash, resumen de nivel y resultado final."""

    # (umbral de combo, color) de menor a mayor intensidad
    _RANGOS_COMBO = (
        (0, (255, 244, 115)),
        (5, (255, 170, 60)),
        (10, (255, 70, 140)),
        (20, (60, 235, 255)),
    )

    def __init__(self, fuentes, ancho, alto):
        self.fuentes = fuentes
        self.ancho = ancho
        self.alto = alto
        self.panel = pygame.Surface((220, 78), pygame.SRCALPHA)
        self.panel.fill((0, 0, 0, 90))

        # También lo lee/modifica ``procesar_eventos`` (p. ej. al cambiar de
        # idioma) para forzar que el texto del nivel se vuelva a renderizar.
        self.idioma_mostrado = None

        self._nivel_mostrado = None
        self._texto_nivel = None
        self._combo_clave = None
        self._combo_lineas = []
        self._combo_infinito_clave = None
        self._combo_infinito_texto = None
        self._combo_previo = 0
        self._pop_inicio = -10.0
        self._capa_combo_infinito = pygame.Surface(
            (ancho, alto), pygame.SRCALPHA
        )
        self._resumen_clave = None
        self._resumen_lineas = ()

    def dibujar_nivel(self, lienzo, idioma, nivel_hud):
        lienzo.blit(self.panel, (6, 6))
        if nivel_hud != self._nivel_mostrado or idioma != self.idioma_mostrado:
            self._texto_nivel = self.fuentes.base.render(
                f"{texto(idioma, 'level')}: {nivel_hud}", True, (255, 255, 255)
            )
            self._nivel_mostrado = nivel_hud
            self.idioma_mostrado = idioma
        lienzo.blit(self._texto_nivel, (14, 10))

    def dibujar_puntaje(self, lienzo, idioma, puntaje):
        superficie = self.fuentes.combo.render(
            f"{texto(idioma, 'score')}: {puntaje}", True, (255, 221, 87)
        )
        lienzo.blit(superficie, (14, 48))

    def dibujar_combo_y_dash(self, lienzo, idioma, combo_visible, tecla_dash, dash_listo):
        clave = (idioma, combo_visible, tecla_dash, dash_listo)
        if clave != self._combo_clave:
            self._combo_clave = clave
            fuente = self.fuentes.combo
            lineas = []
            if combo_visible > 0:
                lineas.append(
                    fuente.render(
                        f"{texto(idioma, 'combo')} x{combo_visible}", True, (255, 225, 100)
                    )
                )
            estado_dash = texto(idioma, "ready") if dash_listo else "..."
            lineas.append(
                fuente.render(
                    f"{pygame.key.name(tecla_dash).upper()}: "
                    f"{texto(idioma, 'dash')} {estado_dash}",
                    True,
                    (130, 255, 190) if dash_listo else (165, 165, 175),
                )
            )
            self._combo_lineas = lineas
        for indice, linea in enumerate(self._combo_lineas):
            rect = linea.get_rect(topright=(self.ancho - 14, 10 + indice * 26))
            lienzo.blit(linea, rect)

    def dibujar_combo_infinito(self, lienzo, idioma, combo_visible, tiempo):
        if combo_visible <= 0:
            self._combo_previo = 0
            return

        # --- Rango (color/intensidad) -----------------------------------
        rango = 0
        for i, (umbral, _) in enumerate(self._RANGOS_COMBO):
            if combo_visible >= umbral:
                rango = i
        color = self._RANGOS_COMBO[rango][1]

        # --- Detectar subida de combo -> dispara el "pop" ----------------
        if combo_visible > self._combo_previo:
            self._pop_inicio = tiempo
        self._combo_previo = combo_visible
        pop = max(0.0, 1.0 - (tiempo - self._pop_inicio) / 0.3)
        pop_suave = pop * pop

        # --- Texto cacheado (solo se re-renderiza si cambia algo) --------
        clave = (idioma, combo_visible, rango)
        if clave != self._combo_infinito_clave:
            self._combo_infinito_clave = clave
            fuente_num = _fuente_negrita(70)
            fuente_eti = _fuente_negrita(24)
            numero = f"x{combo_visible}"
            etiqueta = texto(idioma, "combo").upper()

            num_base = fuente_num.render(numero, True, color)
            num_borde = fuente_num.render(numero, True, (30, 8, 36))
            eti_base = fuente_eti.render(etiqueta, True, (255, 255, 255))
            eti_borde = fuente_eti.render(etiqueta, True, (30, 8, 36))

            ancho_s = max(num_base.get_width(), eti_base.get_width()) + 20
            alto_s = num_base.get_height() + eti_base.get_height() + 16
            superficie = pygame.Surface((ancho_s, alto_s), pygame.SRCALPHA)
            offsets = ((-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, 2), (-2, 2), (2, -2))

            def pegar(base, borde, centro_y):
                for dx, dy in offsets:
                    superficie.blit(
                        borde, borde.get_rect(center=(ancho_s // 2 + dx, centro_y + dy))
                    )
                superficie.blit(base, base.get_rect(center=(ancho_s // 2, centro_y)))

            pegar(eti_base, eti_borde, 10 + eti_base.get_height() // 2)
            pegar(
                num_base, num_borde,
                10 + eti_base.get_height() + num_base.get_height() // 2,
            )
            self._combo_infinito_texto = superficie

        centro_x = self.ancho // 2
        centro_y = int(self.alto * 0.17)

        # --- Capa de efectos (solo bordes y alrededor del número) --------
        capa = self._capa_combo_infinito
        capa.fill((0, 0, 0, 0))

        # Estelas finas en los bordes laterales (a partir de combo x5)
        if rango >= 1:
            for i in range(3 + rango * 2):
                velocidad = 500 + i * 130 + rango * 120
                y = int((tiempo * velocidad + i * 137) % (self.alto + 120)) - 60
                largo = 40 + (i * 29) % 60
                x_izq = 5 + (i % 3) * 5
                x_der = self.ancho - 5 - (i % 3) * 5
                alfa = 55 + rango * 15
                pygame.draw.line(capa, (*color, alfa), (x_izq, y), (x_izq, y + largo), 2)
                pygame.draw.line(capa, (*color, alfa), (x_der, y), (x_der, y + largo), 2)

        if pop > 0:
            # Destello en el marco de la pantalla
            pygame.draw.rect(
                capa,
                (*color, int(70 * pop_suave)),
                capa.get_rect(),
                width=6 + rango * 2,
            )
            # Anillo expansivo
            radio = int(36 + 110 * (1.0 - pop))
            pygame.draw.circle(
                capa, (*color, int(190 * pop_suave)), (centro_x, centro_y), radio, 3
            )
            # Líneas de velocidad cortas alrededor del número
            separacion = 60 + 150 * (1.0 - pop)
            for i in range(10):
                ang = i * math.pi / 5 + 0.3
                x0 = centro_x + math.cos(ang) * separacion
                y0 = centro_y + math.sin(ang) * separacion * 0.6
                x1 = centro_x + math.cos(ang) * (separacion + 34)
                y1 = centro_y + math.sin(ang) * (separacion + 34) * 0.6
                pygame.draw.line(
                    capa, (*color, int(210 * pop)), (x0, y0), (x1, y1), 3
                )
        lienzo.blit(capa, (0, 0))

        # --- Número con pop, temblor e inclinación ----------------------
        escala = 1.0 + 0.6 * pop_suave + 0.025 * (1 + rango) * math.sin(tiempo * 10)
        rotacion = 9.0 * pop * (1 if combo_visible % 2 else -1) + 1.5 * math.sin(tiempo * 7)
        sacudida = (2 + rango) * pop
        dx = random.uniform(-sacudida, sacudida)
        dy = random.uniform(-sacudida, sacudida)

        texto_animado = pygame.transform.rotozoom(
            self._combo_infinito_texto, rotacion, escala
        )
        lienzo.blit(
            texto_animado,
            texto_animado.get_rect(center=(centro_x + dx, centro_y + dy)),
        )

    def dibujar_resumen_nivel(self, lienzo, idioma, nivel_superado, mejor_combo):
        clave = (idioma, nivel_superado, mejor_combo)
        if clave != self._resumen_clave:
            self._resumen_clave = clave
            self._resumen_lineas = (
                self.fuentes.resumen.render(
                    f"{texto(idioma, 'level_clear')} {nivel_superado}", True, (255, 245, 205)
                ),
                self.fuentes.combo.render(
                    f"{texto(idioma, 'best_combo')} x{mejor_combo}", True, (255, 215, 105)
                ),
            )
        for linea, y in zip(self._resumen_lineas, (58, 92)):
            lienzo.blit(linea, linea.get_rect(center=(self.ancho // 2, y)))

    def dibujar_resultado_infinito(self, lienzo, idioma, puntaje, mejor_puntaje):
        resultado = self.fuentes.resumen.render(
            f"{texto(idioma, 'score')}: {puntaje}", True, (255, 245, 205)
        )
        record = self.fuentes.combo.render(
            f"{texto(idioma, 'best_score')}: {mejor_puntaje}", True, (255, 221, 87)
        )
        centro_x = self.ancho // 2
        lienzo.blit(resultado, resultado.get_rect(center=(centro_x, self.alto // 2 + 2)))
        lienzo.blit(record, record.get_rect(center=(centro_x, self.alto // 2 + 31)))