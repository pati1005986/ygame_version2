"""Animación procedural de game over: la recaída, en pixel art.

Todo se dibuja con código (sin imágenes) a 320x240 y se escala sin suavizado.

Qué se ve:
    * Un cuarto de noche con lluvia en la ventana. Al principio la ciudad tiene
      luces encendidas y la planta está erguida; con el deterioro las luces de la
      ciudad se apagan una a una, la planta se marchita y el póster pierde color.
    * Sobre la mesa: una botella volcada que gotea, pastillas regadas y un vaso.
    * El personaje con trazo de pixel art: contorno de 1 px, sombreado en 3 tonos
      y tramado (dithering) en vez de degradados suaves.
    * Rostro detallado: cejas tristes, ojos con iris, pupila y brillo que se
      apaga, venitas rojas, párpados que pesan, ojeras tramadas, mejillas
      hundidas, barba que crece, arrugas, nariz enrojecida, labios agrietados que
      tiemblan y lágrimas que resbalan por las mejillas.
    * La cabeza se inclina sin rotar los píxeles (cizalla por filas), así los
      píxeles se mantienen nítidos.

Uso:
    anim = AnimacionDecaimiento(ancho_pantalla, alto_pantalla)
    anim.dibujar(pantalla, segundos_desde_el_game_over)
"""

import math

import pygame


ANCHO, ALTO = 320, 240
CW, CH = 84, 100                 # tamaño del sprite de la cabeza
PAD = 16                         # margen lateral para la inclinación

CONTORNO = (13, 14, 22)
BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))
LADOS = ((-1, 0), (1, 0), (0, -1), (0, 1))


# ----------------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------------
def _mezclar_color(inicio, fin, cantidad):
    cantidad = max(0.0, min(1.0, cantidad))
    return tuple(
        round(a + (b - a) * cantidad) for a, b in zip(inicio, fin)
    )


def _acotar(v, a=0.0, b=1.0):
    return max(a, min(b, v))


def _tramar(sup, rect, color, fase=0, paso=2):
    """Rellena un rectángulo con un tablero de ajedrez (dithering)."""
    x0, y0, w, h = rect
    for y in range(y0, y0 + h):
        for x in range(x0 + ((y + fase) % paso), x0 + w, paso):
            sup.set_at((x, y), color)


def _elipse_tramada(sup, rect, color, fase=0, paso=2):
    """Elipse rellena con tramado."""
    x0, y0, w, h = rect
    cx, cy = x0 + (w - 1) / 2, y0 + (h - 1) / 2
    rx, ry = w / 2, h / 2
    for y in range(y0, y0 + h):
        dy = ((y - cy) / ry) ** 2
        if dy > 1:
            continue
        for x in range(x0, x0 + w):
            if dy + ((x - cx) / rx) ** 2 <= 1 and (x + y + fase) % paso == 0:
                sup.set_at((x, y), color)


def _contornear(sup, color=CONTORNO):
    """Devuelve una copia con contorno de 1 px alrededor de lo no transparente."""
    mascara = pygame.mask.from_surface(sup)
    borde = mascara.to_surface(setcolor=tuple(color) + (255,), unsetcolor=(0, 0, 0, 0))
    salida = pygame.Surface(sup.get_size(), pygame.SRCALPHA)
    for dx, dy in LADOS:
        salida.blit(borde, (dx, dy))
    salida.blit(sup, (0, 0))
    return salida


def _crear_tira_tramada():
    """Seis filas con densidad creciente de píxeles blancos (transición tramada)."""
    tira = pygame.Surface((ANCHO, 6), pygame.SRCALPHA)
    for k in range(6):
        umbral = (k + 0.5) / 6.0
        for x in range(ANCHO):
            if BAYER[k & 3][x & 3] / 16.0 < umbral:
                tira.set_at((x, k), (255, 255, 255, 255))
    return tira


def _crear_vinetas():
    """Tres capas de viñeta tramada (cada vez más cerradas)."""
    capas = []
    for inicio in (0.80, 0.64, 0.50):
        s = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
        for y in range(ALTO):
            dy = ((y - ALTO / 2) / (ALTO / 2)) ** 2
            for x in range(ANCHO):
                r = math.sqrt(dy + ((x - ANCHO / 2) / (ANCHO / 2)) ** 2)
                if r <= inicio:
                    continue
                g = min(1.0, (r - inicio) / 0.5)
                if g * 16 > BAYER[y & 3][x & 3]:
                    s.set_at((x, y), (3, 4, 9, 255))
        capas.append(s)
    return capas


# ----------------------------------------------------------------------------
# Animación
# ----------------------------------------------------------------------------
class AnimacionDecaimiento:
    """Retrato en pixel art que se va apagando, con movimiento continuo."""

    # edificios de la ciudad vistos por la ventana: (x, y, ancho, alto)
    EDIFICIOS = ((207, 96, 14, 43), (222, 84, 12, 55), (236, 100, 16, 39),
                 (254, 90, 13, 49), (268, 104, 12, 35))

    def __init__(self, ancho, alto):
        self.ancho = ancho
        self.alto = alto
        self.baja = pygame.Surface((ANCHO, ALTO))
        self.personaje = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
        self.cabeza = pygame.Surface((CW, CH), pygame.SRCALPHA)
        self._capa = pygame.Surface((CW, CH), pygame.SRCALPHA)
        self._inc = pygame.Surface((CW + 2 * PAD, CH), pygame.SRCALPHA)
        self._ojo = pygame.Surface((18, 10), pygame.SRCALPHA)
        self._ojo_m = pygame.Surface((18, 10), pygame.SRCALPHA)
        self._luz = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
        self._tira = _crear_tira_tramada()
        self._vinetas = _crear_vinetas()
        self._cache_fondo = {}
        self._cache_mesa = {}

        # luces de las ventanas de los edificios (posición, umbral de apagado)
        self._luces = []
        n = 0
        for (ex, ey, ew, eh) in self.EDIFICIOS:
            for ly in range(ey + 4, ey + eh - 3, 6):
                for lx in range(ex + 3, ex + ew - 3, 5):
                    umbral = ((n * 37 + 11) % 100) / 100.0
                    self._luces.append((lx, ly, umbral, n))
                    n += 1

    # ------------------------------------------------------------------ fondo
    def _fondo(self, d):
        clave = round(d * 24)
        s = self._cache_fondo.get(clave)
        if s is None:
            s = self._construir_fondo(clave / 24.0)
            self._cache_fondo[clave] = s
        return s

    def _construir_fondo(self, d):
        s = pygame.Surface((ANCHO, ALTO))
        arriba = _mezclar_color((82, 88, 76), (25, 27, 37), d)
        abajo = _mezclar_color((54, 63, 59), (11, 14, 23), d)

        # pared con bandas y transición tramada
        bandas = 10
        cols = [_mezclar_color(arriba, abajo, i / (bandas - 1)) for i in range(bandas)]
        alto_b = ALTO / bandas
        for i, c in enumerate(cols):
            pygame.draw.rect(s, c, (0, int(i * alto_b), ANCHO, int(alto_b) + 1))
        for i in range(1, bandas):
            yb = int(i * alto_b) - 3
            pygame.draw.rect(s, cols[i - 1], (0, yb, ANCHO, 6))
            tira = self._tira.copy()
            tira.fill(tuple(cols[i]) + (255,), special_flags=pygame.BLEND_RGBA_MULT)
            s.blit(tira, (0, yb))

        # grietas y manchas de humedad en la pared
        mancha = _mezclar_color((46, 56, 52), (9, 12, 20), d)
        for (mx, my, mw, mh) in ((92, 28, 26, 14), (150, 56, 18, 10), (122, 110, 22, 12)):
            _elipse_tramada(s, (mx, my, mw, mh), mancha)
        grieta = _mezclar_color((38, 44, 42), (6, 8, 14), d)
        pygame.draw.lines(s, grieta, False, [(176, 24), (179, 34), (176, 41), (181, 52)], 1)

        self._poster(s, d)
        self._ventana(s, d)
        self._planta(s, d)
        return s

    def _poster(self, s, d):
        marco = (26, 28, 36)
        papel = _mezclar_color((226, 208, 160), (74, 76, 86), d)
        cielo = _mezclar_color((236, 160, 100), (60, 64, 78), d)
        sol = _mezclar_color((255, 226, 130), (96, 98, 106), d)
        mont = _mezclar_color((70, 98, 96), (32, 36, 46), d)
        suelo = _mezclar_color((52, 70, 70), (26, 30, 38), d)
        txt = _mezclar_color((250, 240, 210), (96, 98, 108), d)
        pygame.draw.rect(s, marco, (28, 42, 48, 62))
        pygame.draw.rect(s, papel, (31, 45, 42, 56))
        pygame.draw.rect(s, cielo, (31, 45, 42, 34))
        pygame.draw.circle(s, sol, (52, 66), 6)
        pygame.draw.polygon(s, mont, [(31, 79), (40, 62), (48, 72), (58, 58), (73, 79)])
        pygame.draw.rect(s, suelo, (31, 79, 42, 22))
        pygame.draw.rect(s, txt, (38, 86, 28, 2))
        pygame.draw.rect(s, txt, (42, 91, 20, 2))
        pygame.draw.rect(s, _mezclar_color((220, 210, 170), (70, 70, 76), d), (40, 39, 8, 4))

    def _ventana(self, s, d):
        cielo_a = _mezclar_color((196, 150, 120), (18, 22, 34), d)
        cielo_b = _mezclar_color((236, 196, 140), (40, 46, 64), d)
        for y in range(24, 139):
            pygame.draw.line(s, _mezclar_color(cielo_a, cielo_b, (y - 24) / 115.0),
                             (205, y), (280, y))
        edif = _mezclar_color((34, 38, 52), (12, 14, 22), d)
        for (ex, ey, ew, eh) in self.EDIFICIOS:
            pygame.draw.rect(s, edif, (ex, ey, ew, eh))
        marco = (36, 38, 46)
        pygame.draw.rect(s, marco, (203, 22, 80, 3))
        pygame.draw.rect(s, marco, (203, 22, 3, 119))
        pygame.draw.rect(s, marco, (281, 22, 3, 119))
        pygame.draw.rect(s, marco, (241, 24, 3, 115))
        pygame.draw.rect(s, marco, (205, 78, 76, 3))
        repisa = _mezclar_color((120, 96, 76), (40, 38, 48), d)
        pygame.draw.rect(s, repisa, (199, 139, 90, 5))
        pygame.draw.rect(s, _mezclar_color((160, 130, 100), (58, 56, 68), d), (199, 139, 90, 1))

    def _planta(self, s, d):
        maceta = _mezclar_color((176, 98, 70), (62, 40, 44), d)
        pygame.draw.polygon(s, maceta, [(214, 128), (232, 128), (229, 139), (217, 139)])
        pygame.draw.rect(s, _mezclar_color((210, 128, 90), (80, 54, 56), d), (213, 127, 20, 2))
        hoja = _mezclar_color((72, 150, 84), (100, 86, 58), d)
        punta = _mezclar_color((110, 190, 110), (120, 100, 66), d)
        for base in (-0.9, -0.3, 0.3, 0.9):
            ang = base + (1 if base > 0 else -1) * d * 1.3      # se va doblando
            largo = 17 - 3 * d
            ex = 223 + math.sin(ang) * largo
            ey = 127 - math.cos(ang) * largo
            pygame.draw.line(s, hoja, (223, 127), (round(ex), round(ey)), 2)
            pygame.draw.rect(s, punta, (round(ex) - 1, round(ey) - 1, 3, 3))

    def _dibujar_ventana(self, t, d):
        # luces de la ciudad que se van apagando
        base = _mezclar_color((246, 214, 130), (120, 110, 90), d)
        for lx, ly, umbral, n in self._luces:
            if 210 <= lx <= 236 and ly > 112:
                continue                                   # detrás de la planta
            limite = d * 0.95
            if umbral > limite or (umbral > limite - 0.06 and math.sin(t * 7 + n) > 0.2):
                pygame.draw.rect(self.baja, base, (lx, ly, 2, 2))

        # lluvia sobre el cristal
        lluvia = _mezclar_color((150, 172, 196), (66, 80, 104), d)
        for i in range(16):
            x = 207 + (i * 17) % 72
            y = 24 + int((i * 29 + t * (38 + (i % 5) * 9)) % 113)
            pygame.draw.rect(self.baja, lluvia, (x, y, 1, 3))
        for i in range(8):                                  # gotas pegadas al vidrio
            gx = 209 + (i * 23) % 68
            gy = 30 + (i * 41) % 100
            pygame.draw.rect(self.baja, lluvia, (gx, gy, 1, 1))

    def _dibujar_luz(self, t, d):
        """Haz de luz frío de la ventana que se debilita."""
        fuerza = int(30 * (1 - d) + 6)
        self._luz.fill((0, 0, 0, 0))
        pygame.draw.polygon(self._luz, (214, 224, 200, fuerza),
                            [(207, 26), (279, 26), (236, 204), (90, 204)])
        self.baja.blit(self._luz, (0, 0))

    # ------------------------------------------------------------------ mesa
    def _mesa(self, d):
        clave = round(d * 12)
        s = self._cache_mesa.get(clave)
        if s is None:
            s = self._construir_mesa(clave / 12.0)
            self._cache_mesa[clave] = s
        return s

    def _construir_mesa(self, d):
        s = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
        top = _mezclar_color((96, 68, 54), (36, 32, 42), d)
        top_l = _mezclar_color((142, 106, 80), (58, 54, 66), d)
        frente = _mezclar_color((58, 40, 36), (20, 18, 26), d)
        veta = _mezclar_color((74, 52, 44), (28, 25, 34), d)
        pygame.draw.rect(s, top, (0, 203, ANCHO, 12))
        pygame.draw.rect(s, top_l, (0, 203, ANCHO, 1))
        pygame.draw.rect(s, frente, (0, 215, ANCHO, ALTO - 215))
        pygame.draw.rect(s, top_l, (0, 215, ANCHO, 1))
        for i in range(14):
            x = (i * 47 + 9) % ANCHO
            y = 205 + (i * 5) % 9
            pygame.draw.line(s, veta, (x, y), (x + 14 + i % 7, y))
        for i in range(9):
            x = (i * 61 + 20) % ANCHO
            y = 219 + (i * 7) % 18
            pygame.draw.line(s, _mezclar_color(frente, (0, 0, 0), 0.35), (x, y), (x + 20 + i % 9, y))

        # líquido derramado
        liquido = _mezclar_color((170, 112, 48), (70, 52, 40), d)
        pygame.draw.ellipse(s, liquido, (106, 207, 24, 5))
        s.set_at((112, 208), _mezclar_color(liquido, (255, 255, 255), 0.4))

        # objetos (se dibujan aparte para contornearlos)
        obj = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)

        # botella volcada
        vidrio = _mezclar_color((52, 112, 84), (28, 44, 46), d)
        vidrio_l = _mezclar_color((110, 176, 140), (52, 76, 76), d)
        vidrio_s = _mezclar_color(vidrio, (0, 0, 0), 0.4)
        pygame.draw.rect(obj, vidrio, (52, 195, 38, 14))
        pygame.draw.ellipse(obj, vidrio, (46, 195, 12, 14))
        pygame.draw.polygon(obj, vidrio, [(90, 195), (98, 199), (98, 205), (90, 209)])
        pygame.draw.rect(obj, vidrio, (98, 199, 12, 6))
        pygame.draw.rect(obj, vidrio_l, (109, 198, 3, 8))
        _tramar(obj, (48, 205, 48, 4), vidrio_s)
        papel = _mezclar_color((216, 206, 170), (96, 92, 84), d)
        pygame.draw.rect(obj, papel, (60, 197, 20, 10))
        pygame.draw.line(obj, (40, 36, 40), (63, 200), (76, 200))
        pygame.draw.line(obj, (40, 36, 40), (63, 203), (72, 203))
        pygame.draw.line(obj, vidrio_l, (52, 196), (88, 196))

        # frasco de pastillas volcado
        ambar = _mezclar_color((190, 112, 36), (74, 52, 36), d)
        pygame.draw.rect(obj, ambar, (152, 198, 20, 10))
        pygame.draw.rect(obj, _mezclar_color((236, 230, 220), (100, 100, 108), d), (172, 199, 5, 8))
        pygame.draw.rect(obj, _mezclar_color((236, 230, 220), (100, 100, 108), d), (156, 200, 10, 6))
        pygame.draw.line(obj, (60, 40, 30), (158, 202), (164, 202))
        pygame.draw.line(obj, _mezclar_color(ambar, (255, 220, 160), 0.5), (153, 199), (170, 199))

        # pastillas regadas
        blanca = _mezclar_color((240, 236, 226), (118, 118, 126), d)
        roja = _mezclar_color((206, 70, 70), (84, 46, 54), d)
        azul = _mezclar_color((90, 130, 210), (50, 62, 90), d)
        for i, (px, py) in enumerate(((132, 206), (138, 209), (143, 204), (147, 208), (127, 210))):
            if i % 2 == 0:
                pygame.draw.rect(obj, blanca, (px, py, 3, 2))
            else:
                pygame.draw.rect(obj, roja, (px, py, 2, 2))
                pygame.draw.rect(obj, azul, (px + 2, py, 2, 2))

        # vaso
        cristal = _mezclar_color((170, 196, 204), (70, 84, 96), d)
        brillo = _mezclar_color((226, 240, 244), (110, 126, 140), d)
        pygame.draw.polygon(obj, cristal, [(250, 189), (268, 189), (266, 209), (252, 209)])
        pygame.draw.polygon(obj, _mezclar_color((176, 120, 52), (68, 50, 40), d),
                            [(251, 200), (267, 200), (266, 209), (252, 209)])
        pygame.draw.line(obj, brillo, (250, 189), (268, 189))
        pygame.draw.line(obj, brillo, (254, 191), (254, 198))

        s.blit(_contornear(obj), (0, 0))
        return s

    def _dibujar_goteo(self, t, d):
        """Una gota que cae del cuello de la botella."""
        u = (t * 0.7) % 1.0
        y = 204 + int(u * 5)
        liquido = _mezclar_color((170, 112, 48), (70, 52, 40), d)
        pygame.draw.rect(self.baja, liquido, (108, y, 1, 2))
        if u > 0.85:                                    # ondita en el charco
            pygame.draw.line(self.baja, _mezclar_color(liquido, (255, 255, 255), 0.35),
                             (105, 209), (111, 209))

    # ------------------------------------------------------------------ torso
    def _dibujar_torso(self, t, d, hy, cab_y):
        P = self.personaje
        cam = _mezclar_color((100, 106, 96), (36, 40, 52), d)
        cam_s = _mezclar_color((62, 68, 64), (20, 22, 32), d)
        cam_l = _mezclar_color((128, 134, 118), (54, 60, 74), d)
        interior = _mezclar_color((30, 32, 40), (12, 13, 20), d)

        pygame.draw.polygon(
            P, cam,
            [(36, 240), (48, hy + 16), (80, hy - 4), (120, hy - 13), (160, hy - 6),
             (200, hy - 13), (240, hy - 4), (272, hy + 16), (284, 240)],
        )
        # lado izquierdo en sombra (la luz viene de la ventana, a la derecha)
        pygame.draw.polygon(
            P, cam_s,
            [(36, 240), (48, hy + 16), (80, hy - 4), (120, hy - 13), (128, hy - 10), (118, 240)],
        )
        _tramar(P, (118, hy - 8, 9, 240 - (hy - 8)), cam_s)
        _tramar(P, (127, hy - 6, 4, 240 - (hy - 6)), cam_s, fase=1, paso=4)
        # hombro derecho iluminado
        pygame.draw.polygon(
            P, cam_l,
            [(204, hy - 11), (240, hy - 4), (272, hy + 16), (264, hy + 22), (238, hy + 4), (204, hy - 6)],
        )
        _tramar(P, (196, hy - 8, 8, 28), cam_l, fase=1)

        # pliegues de la tela (más marcados al encorvarse)
        for (a, b) in (((88, hy + 10), (100, hy + 36)), ((232, hy + 10), (222, hy + 32)),
                       ((60, hy + 24), (68, hy + 44)), ((254, hy + 26), (246, hy + 46))):
            pygame.draw.line(P, cam_s, a, b, 1)

        # cuello de la sudadera
        pygame.draw.polygon(P, interior, [(126, hy - 12), (160, hy + 14), (194, hy - 12)])

        cuello = _mezclar_color((176, 140, 116), (80, 86, 96), d)
        cuello_s = _mezclar_color((118, 84, 78), (40, 46, 58), d)
        ny0 = cab_y + 78
        nh = hy + 4 - ny0
        pygame.draw.rect(P, cuello, (143, ny0, 34, nh))
        pygame.draw.rect(P, cuello_s, (143, ny0, 8, nh))
        _tramar(P, (151, ny0, 5, nh), cuello_s)
        chin = cab_y + 90                                   # sombra bajo la barbilla
        pygame.draw.rect(P, cuello_s, (143, chin, 34, 6))
        _tramar(P, (143, chin + 6, 34, 4), cuello_s)
        pygame.draw.line(P, cuello_s, (150, chin + 8), (154, hy + 2), 1)
        pygame.draw.line(P, cuello_s, (170, chin + 8), (166, hy + 2), 1)

        # borde del cuello de la sudadera por delante
        pygame.draw.line(P, cam_l, (126, hy - 12), (146, hy + 4), 2)
        pygame.draw.line(P, cam_l, (194, hy - 12), (174, hy + 4), 2)
        pygame.draw.line(P, cam_s, (126, hy - 10), (146, hy + 6), 1)

        # cordones que se balancean con la respiración
        cord = _mezclar_color((200, 200, 186), (84, 86, 96), d)
        sw = round(math.sin(t * 1.35 + 0.5))
        pygame.draw.line(P, cord, (149, hy + 8), (147 + sw, hy + 38), 1)
        pygame.draw.line(P, cord, (171, hy + 8), (173 + sw, hy + 34), 1)
        pygame.draw.rect(P, cord, (146 + sw, hy + 38, 3, 3))
        pygame.draw.rect(P, cord, (172 + sw, hy + 34, 3, 3))

    # ------------------------------------------------------------------ cabeza
    def _inclinar(self, sup, k, pivote):
        """Inclina el sprite desplazando filas (sin rotar píxeles)."""
        self._inc.fill((0, 0, 0, 0))
        for y in range(CH):
            dx = round((y - pivote) * k)
            self._inc.blit(sup, (PAD + dx, y), (0, y, CW, 1))
        return self._inc

    def _dibujar_cabeza(self, t, d, sob):
        h = self.cabeza
        h.fill((0, 0, 0, 0))

        piel = _mezclar_color((216, 180, 148), (118, 124, 132), d)
        piel_m = _mezclar_color((192, 148, 122), (88, 94, 108), d)
        sombra = _mezclar_color((146, 102, 96), (50, 56, 70), d)
        luz = _mezclar_color((240, 212, 180), (152, 158, 168), d)
        pelo = _mezclar_color((30, 27, 38), (20, 20, 28), d)
        brillo_p = _mezclar_color((84, 90, 122), (40, 44, 60), d)
        lloro = _acotar((d - 0.3) / 0.3)

        # --- silueta de la cara (mandíbula más estrecha con el deterioro) ---
        jaw = round(3 * d)
        cara = [(20, 14), (64, 14), (72, 28), (74, 50), (70 - jaw, 68), (62 - jaw, 84),
                (50, 93), (34, 93), (22 + jaw, 84), (14 + jaw, 68), (10, 50), (12, 28)]
        pygame.draw.polygon(h, piel, cara)
        pygame.draw.ellipse(h, piel, (4, 47, 10, 17))
        pygame.draw.ellipse(h, piel, (70, 47, 10, 17))
        mask_surf = pygame.mask.from_surface(h).to_surface(
            setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))

        # --- sombreado en capa aparte, recortado a la silueta ---
        c = self._capa
        c.fill((0, 0, 0, 0))

        # lado izquierdo en sombra con borde tramado
        for y in range(14, 95):
            e = 20 + int(2 * math.sin(y / 9.0))
            pygame.draw.line(c, sombra, (0, y), (e, y))
            for x in range(e + 1, e + 5):
                if (x + y) % 2 == 0:
                    c.set_at((x, y), sombra)
            for x in range(e + 5, e + 9):
                if (x + 2 * y) % 4 == 0:
                    c.set_at((x, y), sombra)
        # luces del lado derecho
        _elipse_tramada(c, (46, 18, 20, 10), luz)
        pygame.draw.ellipse(c, luz, (50, 21, 12, 5))
        _elipse_tramada(c, (48, 52, 18, 8), luz, fase=1)

        # cuencas hundidas bajo las cejas
        if d > 0.25:
            _elipse_tramada(c, (15, 38, 24, 7), sombra)
            _elipse_tramada(c, (45, 38, 24, 7), sombra)

        # ojeras tramadas (más marcadas con el deterioro)
        ojera = _mezclar_color(piel, (88, 66, 108), 0.18 + 0.5 * d)
        for ox in (16, 46):
            _elipse_tramada(c, (ox, 51, 22, 11), ojera)
            pygame.draw.ellipse(c, ojera, (ox + 2, 53, 18, 6))

        # mejillas hundidas
        if d > 0.15:
            paso = 2 if d > 0.55 else 3
            _elipse_tramada(c, (14, 62, 14, 18), sombra, paso=paso)
            _elipse_tramada(c, (56, 62, 14, 18), sombra, fase=1, paso=paso)

        # barba descuidada que crece
        if d > 0.05:
            barba = _mezclar_color(piel, (30, 28, 38), 0.5)
            dens = 1 + int(d * 5)
            for y in range(66, 93):
                dy = ((y - 70) / 24.0) ** 2
                for x in range(16, 69):
                    if dy + ((x - 42) / 27.0) ** 2 <= 1 and (x * 7 + y * 13) % 9 < dens:
                        c.set_at((x, y), barba)

        # nariz: puente, punta, aletas y fosas
        pygame.draw.line(c, sombra, (40, 44), (39, 64), 1)
        pygame.draw.line(c, luz, (44, 46), (45, 62), 1)
        pygame.draw.ellipse(c, piel_m, (37, 62, 10, 8))
        pygame.draw.ellipse(c, luz, (41, 62, 4, 3))
        pygame.draw.line(c, sombra, (36, 64), (36, 69), 1)
        pygame.draw.line(c, sombra, (48, 64), (48, 69), 1)
        pygame.draw.rect(c, sombra, (36, 70, 12, 2))
        pygame.draw.rect(c, CONTORNO, (38, 69, 3, 2))
        pygame.draw.rect(c, CONTORNO, (44, 69, 3, 2))
        pygame.draw.line(c, piel_m, (40, 72), (40, 77), 1)
        pygame.draw.line(c, piel_m, (44, 72), (44, 77), 1)

        # arrugas: frente, patas de gallo y surcos de la nariz a la boca
        if d > 0.3:
            pygame.draw.line(c, piel_m, (26, 24), (38, 24))
            pygame.draw.line(c, piel_m, (46, 24), (58, 24))
            pygame.draw.line(c, piel_m, (30, 28), (54, 28))
        if d > 0.4:
            for (a, b) in (((66, 42), (70, 41)), ((66, 45), (71, 46)),
                           ((18, 42), (14, 41)), ((18, 45), (13, 46))):
                pygame.draw.line(c, piel_m, a, b, 1)
        if d > 0.15:
            ancho_s = 2 if d > 0.5 else 1
            pygame.draw.line(c, piel_m, (35, 63), (31, 77), ancho_s)
            pygame.draw.line(c, piel_m, (49, 63), (53, 77), ancho_s)

        # oreja: pliegue interior
        pygame.draw.ellipse(c, sombra, (6, 51, 4, 8), 1)
        pygame.draw.ellipse(c, piel_m, (74, 51, 4, 8), 1)

        c.blit(mask_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        h.blit(c, (0, 0))

        # --- pelo grasoso y desordenado ---
        s = [round(d * 3 + 1.2 * math.sin(t * 1.3 + i)) for i in range(5)]
        fleco = [(70, 32), (65, 38 + s[0]), (59, 32), (54, 40 + s[1]), (48, 33),
                 (42, 39 + s[2]), (36, 32), (30, 38 + s[3]), (24, 31),
                 (18, 37 + s[4]), (13, 33)]
        casco = [(6, 52), (4, 34), (7, 18), (18, 6), (36, 1), (54, 2), (70, 9),
                 (79, 22), (80, 38), (78, 54), (73, 52), (72, 34)]
        pygame.draw.polygon(h, pelo, casco + fleco + [(11, 34), (10, 52)])
        for (a, b) in (((30, 6), (42, 4)), ((42, 4), (54, 5)), ((20, 14), (24, 10)),
                       ((60, 10), (68, 14)), ((64, 20), (72, 24))):
            pygame.draw.line(h, brillo_p, a, b, 1)
        if d > 0.35:                                        # mechones sueltos
            for i, (mx, my) in enumerate(((30, 40), (48, 41), (18, 39))):
                sx = round(math.sin(t * 1.1 + i * 2) * 1.5)
                pygame.draw.line(h, pelo, (mx, my + s[i % 5]), (mx + sx - 1, my + 7 + s[i % 5]), 1)

        # --- enrojecimiento de nariz y mejillas por el llanto ---
        if lloro > 0.05:
            rojo = _mezclar_color(piel, (206, 96, 104), 0.6 * lloro)
            _elipse_tramada(h, (37, 61, 10, 8), rojo)
            if lloro > 0.3:
                _elipse_tramada(h, (15, 58, 13, 7), rojo, fase=1)
                _elipse_tramada(h, (56, 58, 13, 7), rojo, fase=1)

        # --- parpadeo: se vuelve lento y pesado ---
        ancho_p = 0.12 + 0.2 * d
        parp = max(0.0, 1 - abs((t % 4.3) - 3.9) / ancho_p)
        parp = max(parp, 0.55 * (max(0.0, math.sin(t * 0.7)) ** 8) * d)

        self._dibujar_ojo(h, 27, 45, -1, t, d, parp, piel_m, sombra)
        self._dibujar_ojo(h, 57, 45, 1, t, d, parp, piel_m, sombra)
        self._dibujar_ceja(h, 27, -1, d, pelo, sombra)
        self._dibujar_ceja(h, 57, 1, d, pelo, sombra)
        self._dibujar_boca(h, t, d, sob, piel, piel_m, sombra, luz)

        # --- lágrimas que resbalan por las mejillas ---
        if lloro > 0.3:
            brillo_l = (196, 226, 246)
            estela = _mezclar_color(piel, (170, 204, 224), 0.55)
            for lado, cx in ((0, 24), (1, 60)):
                u = (t * 0.31 + lado * 0.37) % 1.0
                x0, y0 = cx, 51
                x1 = cx + round(1.6 * math.sin(u * 5 + lado))
                y1 = 51 + int(26 * u)
                pygame.draw.line(h, estela, (x0, y0), (x1, y1), 1)
                pygame.draw.rect(h, brillo_l, (x1 - 1, y1, 2, 3))
                h.set_at((x1 - 1, y1), (255, 255, 255))

        return _contornear(h)

    def _dibujar_ojo(self, h, cx, cy, lado, t, d, parp, piel_m, sombra):
        ancho, alto = 18, 10
        x0, y0 = cx - 9, cy - 5
        lid = round(d * 4.5)                         # párpado que pesa
        tot = lid + round(parp * (alto - lid))
        vis = alto - tot

        if vis <= 1:                                 # ojo cerrado
            pygame.draw.line(h, CONTORNO, (x0 + 1, cy + 1), (x0 + ancho - 2, cy + 1), 2)
            pygame.draw.line(h, sombra, (x0 + 3, cy + 3), (x0 + ancho - 4, cy + 3), 1)
            return

        o = self._ojo
        o.fill((0, 0, 0, 0))
        esclera = _mezclar_color((238, 234, 224), (214, 162, 162), d * 0.9)
        pygame.draw.ellipse(o, esclera, (0, 0, ancho, alto))

        # mirada: errante al principio, perdida y hacia abajo al final
        gx = round(math.sin(t * 0.45 + lado * 0.8) * 3 * (1 - d) - 2 * d)
        gy = round(d * 2)
        ix, iy = 9 + max(-3, min(3, gx)), 5 + gy
        iris = _mezclar_color((72, 120, 126), (58, 64, 78), d)
        pygame.draw.circle(o, _mezclar_color(iris, (10, 14, 22), 0.55), (ix, iy), 4)
        pygame.draw.circle(o, iris, (ix, iy), 3)
        pygame.draw.circle(o, (10, 10, 16), (ix, iy), 2)
        brillo = _mezclar_color((255, 255, 255), iris, d)    # el brillo se apaga
        pygame.draw.rect(o, brillo, (ix - 2, iy - 2, 2, 1))
        o.set_at((ix + 1, iy + 1), _mezclar_color(brillo, (10, 10, 16), 0.4))

        if d > 0.2:                                  # venitas rojas
            rojo = (196, 64, 76)
            pygame.draw.line(o, rojo, (1, 5), (4, 4))
            pygame.draw.line(o, rojo, (2, 6), (5, 6))
            if d > 0.5:
                pygame.draw.line(o, rojo, (16, 5), (13, 4))
                pygame.draw.line(o, rojo, (15, 6), (12, 6))
        if d > 0.4:                                  # ojos vidriosos
            pygame.draw.line(o, (176, 208, 228), (3, 8), (14, 8))

        m = self._ojo_m
        m.fill((0, 0, 0, 0))
        pygame.draw.ellipse(m, (255, 255, 255, 255), (0, 0, ancho, alto))
        if tot > 0:
            m.fill((0, 0, 0, 0), (0, 0, ancho, tot))
        o.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        h.blit(o, (x0, y0))

        # contorno del párpado superior (recto al bajar) e inferior (curvo)
        cyc = cy - 0.5
        yt = y0 + tot
        inf = _mezclar_color(CONTORNO, sombra, 0.4)
        for xi in range(ancho):
            nx = (xi - (ancho - 1) / 2) / (ancho / 2)
            r = math.sqrt(max(0.0, 1 - nx * nx))
            yu = max(round(cyc - 4.5 * r), yt)
            h.set_at((x0 + xi, yu), CONTORNO)
            if 1 <= xi <= ancho - 2:
                h.set_at((x0 + xi, yu - 1), sombra)              # pliegue del párpado
                if tot >= 2:
                    h.set_at((x0 + xi, yu + 1), _mezclar_color(CONTORNO, (214, 162, 162), 0.5))
            h.set_at((x0 + xi, round(cyc + 4.5 * r)), inf)

        # pestaña externa
        if lado < 0:
            h.set_at((x0 - 1, cy - 1), CONTORNO)
            h.set_at((x0 - 2, cy - 2), CONTORNO)
        else:
            h.set_at((x0 + ancho, cy - 1), CONTORNO)
            h.set_at((x0 + ancho + 1, cy - 2), CONTORNO)

    def _dibujar_ceja(self, h, cx, lado, d, pelo, sombra):
        by = 35 + round(d * 1.5)
        exterior = (cx + lado * 10, by + 1 + round(d * 1.5))
        interior = (cx - lado * 9, by - round(d * 3))      # interior elevado: tristeza
        medio = (cx + lado * 2, by - 1 - round(d))
        pygame.draw.lines(h, pelo, False, [exterior, medio, interior], 2)
        pygame.draw.line(h, pelo, exterior, (exterior[0] - lado * 2, exterior[1] + 1), 1)
        if d > 0.45:                                         # ceño fruncido
            pygame.draw.line(h, sombra, (41, 33), (41, 39), 1)
            pygame.draw.line(h, sombra, (44, 33), (44, 39), 1)

    def _dibujar_boca(self, h, t, d, sob, piel, piel_m, sombra, luz):
        y = 80
        cd = round(d * 3)                                    # comisuras caídas
        open_h = round(sob * 3 + (0.5 + 0.5 * math.sin(t * 1.1)) * (1 if d > 0.6 else 0))
        temblor = 1 if (d > 0.5 and sob > 0.2 and math.sin(t * 11) > 0.5) else 0
        labio = _mezclar_color((196, 116, 108), (92, 84, 100), d)
        labio_o = _mezclar_color((150, 84, 84), (66, 58, 74), d)

        # labio superior
        pygame.draw.polygon(h, labio_o, [(31, y + cd), (36, y - 3), (42, y - 2),
                                         (48, y - 3), (53, y + cd), (42, y + 1)])
        # interior y dientes
        if open_h > 0:
            pygame.draw.rect(h, (28, 16, 26), (35, y + 1, 14, open_h))
            if open_h >= 2:
                pygame.draw.rect(h, _mezclar_color((226, 220, 205), (120, 120, 124), d),
                                 (37, y + 1, 10, 1))
        # labio inferior (tiembla al sollozar)
        yo = y + 1 + open_h
        pygame.draw.polygon(h, labio, [(34, yo), (50, yo), (48, yo + 4 + temblor),
                                       (42, yo + 5 + temblor), (36, yo + 4 + temblor)])
        h.set_at((41, yo + 2), luz)
        if d > 0.3:                                          # labio agrietado
            h.set_at((44, yo + 2), _mezclar_color(labio_o, (40, 10, 10), 0.4))
            h.set_at((38, yo + 1), _mezclar_color(labio_o, (40, 10, 10), 0.3))
        h.set_at((30, y + 1 + cd), sombra)
        h.set_at((54, y + 1 + cd), sombra)
        pygame.draw.line(h, sombra, (38, y + 10), (46, y + 10), 1)   # pliegue del mentón

    # ------------------------------------------------------------------ cuadro
    def dibujar(self, destino, tiempo):
        """Dibuja la animación para el tiempo transcurrido desde el game over."""
        d = _acotar(tiempo / 10.0)
        resp = math.sin(tiempo * 1.35) * (1.0 - 0.45 * d)
        sob = (max(0.0, math.sin(tiempo * 2.2)) ** 8) * _acotar((d - 0.35) / 0.65)

        self.baja.blit(self._fondo(d), (0, 0))
        self._dibujar_ventana(tiempo, d)
        self._dibujar_luz(tiempo, d)

        # personaje: torso + cabeza inclinada por filas
        self.personaje.fill((0, 0, 0, 0))
        hy = 182 + round(8 * d + resp - 2 * sob)
        cab_y = 62 + round(20 * d + resp * 1.5 + sob * 2)
        self._dibujar_torso(tiempo, d, hy, cab_y)
        cabeza = self._dibujar_cabeza(tiempo, d, sob)
        k = 0.03 + 0.2 * d + 0.012 * math.sin(tiempo * 0.8)
        inc = self._inclinar(cabeza, k, CH - 6)
        cab_x = 160 - inc.get_width() // 2 + round(5 * d)
        self.personaje.blit(inc, (cab_x, cab_y))
        self.baja.blit(_contornear(self.personaje), (0, 0))

        # mesa con la botella, el vaso y las pastillas
        self.baja.blit(self._mesa(d), (0, 0))
        self._dibujar_goteo(tiempo, d)

        # ceniza que se desprende del personaje
        for i in range(26):
            inicio = (i * 0.071) % 0.78
            vida = tiempo - (inicio * 10)
            if d <= 0.12 or vida < 0:
                continue
            vida = (vida * (0.32 + (i % 4) * 0.07)) % 2.4
            x0 = 103 + (i * 29) % 116
            y0 = 91 + (i * 37) % 82
            x = round(x0 + vida * (8 + i % 6))
            y = round(y0 + vida * vida * (7 + i % 3))
            tono = int(110 * (1 - min(1.0, vida / 2.4)))
            pygame.draw.rect(self.baja, (tono, tono + 4, tono + 8),
                             (x, y, 1 + i % 2, 1 + i % 2))

        # viñeta tramada que se cierra con el deterioro
        for capa, umbral in zip(self._vinetas, (-0.1, 0.3, 0.65)):
            a = _acotar((d - umbral) / 0.3)
            if a > 0:
                capa.set_alpha(int(255 * a))
                self.baja.blit(capa, (0, 0))

        # parpadeo de la luz y cortes de señal en la recta final
        if d > 0.42:
            fase = 0.5 + 0.5 * math.sin(tiempo * 1.7)
            overlay = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
            overlay.fill((2, 4, 12, round(30 + 26 * fase * d)))
            self.baja.blit(overlay, (0, 0))
            if math.sin(tiempo * 2.6) > 0.92:
                y = 28 + int((tiempo * 31) % 175)
                tira = self.baja.subsurface((0, y, ANCHO, 6)).copy()
                self.baja.blit(tira, (3 if int(tiempo * 10) % 2 else -3, y))
                pygame.draw.rect(self.baja, (100, 112, 128), (0, y, ANCHO, 1))

        escala = min(self.ancho / ANCHO, self.alto / ALTO)
        tamano = (max(1, round(ANCHO * escala)), max(1, round(ALTO * escala)))
        fotograma = pygame.transform.scale(self.baja, tamano)
        destino.fill((9, 12, 20))
        destino.blit(
            fotograma,
            ((self.ancho - tamano[0]) // 2, (self.alto - tamano[1]) // 2),
        )