"""Plataformas normales y plataformas trampa del juego."""

import colorsys
import math
import random

import pygame


def color_desde_hue(hue, saturacion=0.65, valor=0.95):
    """Convierte un matiz HSV en un color RGB vivo."""
    r, g, b = colorsys.hsv_to_rgb(hue % 1.0, saturacion, valor)
    return int(r * 255), int(g * 255), int(b * 255)


def _mezclar(color_a, color_b, factor):
    """Interpola linealmente entre dos colores RGB (factor entre 0 y 1)."""
    factor = max(0.0, min(1.0, factor))
    return tuple(int(a + (b - a) * factor) for a, b in zip(color_a, color_b))


class Plataforma:
    """Plataforma sólida, opcionalmente disfrazada de trampa vibrante."""

    COLOR_PELIGRO = (235, 60, 55)
    COLOR_HUECO = (22, 13, 35)
    COLOR_HUECO_PROFUNDO = (6, 4, 10)

    def __init__(self, x, y, w, h, hue, es_trampa=False):
        self.rect = pygame.Rect(x, y, w, h)
        self.hue = hue
        self.es_trampa = es_trampa
        self.fase = random.uniform(0, math.tau)
        self.trampa_activada = False
        self.progreso_trampa = 0.0

    def activar_trampa(self):
        """Abre la trampa y comienza a hundir al personaje."""
        if self.es_trampa:
            self.trampa_activada = True

    def actualizar(self):
        """Avanza la animación de la plataforma cuando ya se activó."""
        if self.trampa_activada:
            self.progreso_trampa = min(1.0, self.progreso_trampa + 0.045)

    def dibujar(self, superficie, tiempo, nivel):
        """Dibuja la plataforma con una forma abstracta, más pictórica y
        expresiva, inspirada en composiciones de arte contemporáneo."""
        hue = (self.hue + math.sin(tiempo * 0.6 + self.fase) * 0.05 + nivel * 0.03) % 1.0
        color_base = color_desde_hue(hue, 0.68, 0.96)
        color_sombra = color_desde_hue(hue, 0.75, 0.52)
        color_luz = color_desde_hue(hue, 0.5, 1.0)
        color_acento = color_desde_hue((hue + 0.18) % 1.0, 0.7, 0.9)

        vibracion = 0
        if self.es_trampa and not self.trampa_activada:
            vibracion = int(math.sin(tiempo * 26 + self.fase) * 3)
        rect = self.rect.move(vibracion, 0)

        color_halo = self.COLOR_PELIGRO if (self.es_trampa and self.trampa_activada) else color_base
        self._dibujar_halo(superficie, rect, color_halo)
        self._dibujar_sombra_contacto(superficie, rect)

        # Forma base abstracta: bloque irregular con perfiles orgánicos.
        puntos = self._puntos_plataforma(rect)
        pygame.draw.polygon(superficie, (0, 0, 0), puntos, 3)
        pygame.draw.polygon(superficie, color_sombra, puntos)
        pygame.draw.polygon(superficie, color_base, [(p[0] + 4, p[1] + 2) for p in puntos])

        # Capa superior luminosa, como una franja de pintura de alta energía.
        puntos_luz = [(p[0] + 8, p[1] + 5) for p in puntos[:4]]
        puntos_luz[0] = (puntos_luz[0][0] + 12, puntos_luz[0][1] + 4)
        puntos_luz[1] = (puntos_luz[1][0] - 16, puntos_luz[1][1] + 3)
        pygame.draw.polygon(superficie, color_luz, puntos_luz)
        pygame.draw.polygon(superficie, (0, 0, 0), puntos_luz, 2)

        # Elementos abstractos dentro de la forma: curvas y bloques cromáticos.
        self._dibujar_acento_abstracto(superficie, rect, color_acento, color_sombra, color_luz)

        if self.es_trampa:
            self._dibujar_trampa(superficie, rect, tiempo, color_base)

    def _puntos_plataforma(self, rect):
        """Genera un perfil irregular que parece una pieza orgánica, casi
        escultórica, en lugar de un bloque rígido."""
        margen_x = rect.width * 0.08
        margen_y = rect.height * 0.25
        return [
            (rect.left + margen_x, rect.top + 7),
            (rect.right - margen_x * 0.9, rect.top + 2),
            (rect.right - 6, rect.top + 10),
            (rect.right - 4, rect.bottom - 6),
            (rect.left + 8, rect.bottom - 2),
            (rect.left + 2, rect.top + 16),
        ]

    def _dibujar_acento_abstracto(self, superficie, rect, color_acento, color_sombra, color_luz):
        """Añade manchas y líneas abstractas que simulan pintura gestual sobre
        la plataforma."""
        centro = rect.center
        radio = rect.width * 0.18
        circulo = pygame.Surface((radio * 2, radio * 2), pygame.SRCALPHA)
        pygame.draw.circle(circulo, (*color_acento, 120), (int(radio), int(radio)), int(radio))
        pygame.draw.circle(circulo, (0, 0, 0, 200), (int(radio), int(radio)), int(radio), 2)
        superficie.blit(circulo, (centrox := centro[0] - int(radio), centro[1] - int(radio) + 6))

        r1 = pygame.Rect(rect.left + 20, rect.top + 9, rect.width * 0.23, max(4, rect.height * 0.38))
        pygame.draw.rect(superficie, color_sombra, r1, border_radius=8)
        pygame.draw.rect(superficie, (0, 0, 0), r1, 2, border_radius=8)

        r2 = pygame.Rect(rect.left + rect.width * 0.54, rect.top + 4, rect.width * 0.18, max(6, rect.height * 0.52))
        pygame.draw.rect(superficie, color_luz, r2, border_radius=8)
        pygame.draw.rect(superficie, (0, 0, 0), r2, 2, border_radius=8)

        linea_1 = pygame.Rect(rect.left + 16, rect.centery - 3, rect.width * 0.74, 3)
        pygame.draw.rect(superficie, (*color_acento, 180), linea_1, border_radius=3)
        pygame.draw.rect(superficie, (0, 0, 0), linea_1, 1, border_radius=3)

        tri = [
            (rect.right - 26, rect.top + 12),
            (rect.right - 6, rect.top + 20),
            (rect.right - 20, rect.bottom - 10),
        ]
        pygame.draw.polygon(superficie, color_sombra, tri)
        pygame.draw.polygon(superficie, (0, 0, 0), tri, 2)

    def _dibujar_halo(self, superficie, rect, color):
        """Aura translúcida detrás de la plataforma; se tiñe de rojo cuando
        la trampa ya está activa."""
        radio = rect.height * 1.4
        capa = pygame.Surface((radio * 2, radio * 2), pygame.SRCALPHA)
        pygame.draw.circle(capa, (*color, 55), (radio, radio), radio)
        superficie.blit(capa, (rect.centerx - radio, rect.top - radio * 0.6))

    def _dibujar_sombra_contacto(self, superficie, rect):
        """Sombra elíptica y suave proyectada justo debajo de la plataforma,
        que ancla visualmente la pieza al resto de la escena."""
        alto = max(4, int(rect.height * 0.35))
        ancho = int(rect.width * 0.92)
        if ancho <= 0:
            return
        sombra = pygame.Surface((ancho, alto), pygame.SRCALPHA)
        pygame.draw.ellipse(sombra, (10, 6, 18, 70), sombra.get_rect())
        superficie.blit(sombra, (rect.centerx - ancho // 2, rect.bottom - alto // 3))

    def _dibujar_trampa(self, superficie, rect, tiempo, color_base):
        """Antes de activarse: rayas de peligro que laten y una boca apenas
        entreabierta con dientes, como advertencia. Después de activarse:
        el agujero crece y se oscurece progresivamente (progreso_trampa)
        mientras los dientes rodean todo el borde."""
        abertura = rect.inflate(-12, -5)

        if not self.trampa_activada:
            pulso = 0.5 + 0.5 * math.sin(tiempo * 6 + self.fase)
            color_raya = _mezclar(color_base, self.COLOR_PELIGRO, 0.3 + 0.3 * pulso)
            self._dibujar_rayas_peligro(superficie, rect, color_raya)

            boca_cerrada = abertura.inflate(-abertura.width * 0.5, -abertura.height * 0.3)
            pygame.draw.ellipse(superficie, self.COLOR_HUECO, boca_cerrada)
            self._dibujar_dientes(superficie, boca_cerrada, color_base, largo=5)
        else:
            progreso = self.progreso_trampa
            hueco = abertura.inflate(
                -abertura.width * (1 - progreso) * 0.6,
                -abertura.height * (1 - progreso) * 0.3,
            )
            color_hueco = _mezclar(self.COLOR_HUECO, self.COLOR_HUECO_PROFUNDO, progreso)
            pygame.draw.ellipse(superficie, color_hueco, hueco)
            self._dibujar_dientes(superficie, hueco, color_base, largo=4 + 5 * progreso)

    def _dibujar_rayas_peligro(self, superficie, rect, color_raya):
        """Rayas diagonales tipo cinta de peligro, recortadas a la forma
        redondeada de la plataforma."""
        capa = pygame.Surface(rect.size, pygame.SRCALPHA)
        paso = 10
        for offset in range(-rect.height, rect.width, paso):
            pygame.draw.line(
                capa,
                (*color_raya, 140),
                (offset, rect.height),
                (offset + rect.height, 0),
                4,
            )
        mascara = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(mascara, (255, 255, 255, 255), mascara.get_rect(), border_radius=10)
        capa.blit(mascara, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        superficie.blit(capa, rect.topleft)

    def _dibujar_dientes(self, superficie, abertura, color_base, largo=5, cantidad=12):
        """Dientes triangulares distribuidos en torno a todo el perímetro
        de la abertura (en vez de solo tres, como en la versión original)."""
        radio_x = abertura.width / 2
        radio_y = abertura.height / 2
        if radio_x <= 0 or radio_y <= 0:
            return
        for i in range(cantidad):
            angulo = math.tau * i / cantidad
            coseno, seno = math.cos(angulo), math.sin(angulo)
            base_x = abertura.centerx + coseno * radio_x
            base_y = abertura.centery + seno * radio_y
            punta = (
                abertura.centerx + coseno * (radio_x + largo),
                abertura.centery + seno * (radio_y + largo),
            )
            perp = pygame.Vector2(-seno, coseno) * 2.6
            p1 = (base_x + perp.x, base_y + perp.y)
            p2 = (base_x - perp.x, base_y - perp.y)
            pygame.draw.polygon(superficie, color_base, [p1, p2, punta])