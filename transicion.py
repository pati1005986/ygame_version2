"""Transición caricaturesca entre niveles, sin imágenes ni archivos de audio.

La clase pública ``TransicionCaricaturesca`` se actualiza desde el bucle del
juego y se dibuja encima del nivel. También sintetiza y reproduce un efecto
de sorpresa al comenzar cada transición.
"""

import colorsys
import math
import random
from array import array

import pygame


class TransicionCaricaturesca:
    """Transición de nivel con una cara caricaturesca dibujada con Pygame.

    El diseño se inspira en el trazo grueso y gestual de los "pocket
    cartoons" británicos (línea negra marcada, rasgos muy exagerados,
    pocos colores). Cada transición elige al azar un único matiz y toda
    la cara se pinta en variaciones de ese mismo color (look
    monocromático), así nunca se repite la misma combinación dos veces.
    """

    DURACION_SALIDA = 380
    DURACION_ENTRADA = 680

    NUM_RAYOS = 10
    NUM_PARTICULAS = 14

    # Empieza a decaerse a partir del nivel 10 y alcanza el máximo
    # alrededor del nivel 18. Ajusta estos valores si cambias la curva
    # de progresión del juego.
    NIVEL_INICIO_TRISTEZA = 10
    NIVEL_TRISTEZA_MAXIMA = 18

    def __init__(self, color_origen, color_destino, posicion_origen, posicion_spawn, nivel=0, volumen_efectos=1.0):
        self.inicio = pygame.time.get_ticks()
        self.color_origen = color_origen
        self.color_destino = color_destino
        self.posicion_origen = pygame.Vector2(posicion_origen)
        self.posicion_spawn = pygame.Vector2(posicion_spawn)
        self.finalizada = False
        self.parpadeo = 0.0
        self.volumen_efectos = max(0.0, min(1.0, float(volumen_efectos)))

        # A medida que sube el nivel, la cara se pone más triste/decaída:
        # cejas preocupadas, mirada caída, boca hacia abajo, colores
        # apagados y menos "chispa" en la animación.
        # 0.0 = expresión feliz/sorprendida normal, 1.0 = muy triste.
        self.nivel = nivel
        if nivel < self.NIVEL_INICIO_TRISTEZA:
            self.tristeza = 0.0
        else:
            rango = max(1, self.NIVEL_TRISTEZA_MAXIMA - self.NIVEL_INICIO_TRISTEZA)
            self.tristeza = max(
                0.0,
                min(1.0, (nivel - self.NIVEL_INICIO_TRISTEZA) / rango),
            )

        # Un matiz aleatorio distinto en cada transición; toda la cara
        # se deriva de él (solo cambian saturación y brillo, y ahora
        # también se apagan un poco según la tristeza).
        self.tono = random.random()
        self.paleta = self._generar_paleta(self.tono, self.tristeza)
        self.sonido_sorpresa = self._crear_sonido_sorpresa(self.tristeza)
        if self.sonido_sorpresa:
            self.sonido_sorpresa.set_volume(self.volumen_efectos)
            self.sonido_sorpresa.play()

        # Partículas del chispazo cómico: se calculan una sola vez para
        # que no titilen de un fotograma a otro. Con mucha tristeza casi
        # no hay chispazo: un personaje decaído no "explota" de alegría.
        num_particulas = max(2, int(self.NUM_PARTICULAS * (1.0 - self.tristeza * 0.75)))
        self._particulas = [
            (
                random.uniform(0, math.tau),
                random.uniform(0.55, 1.0),
                random.uniform(2.5, 5.5),
            )
            for _ in range(num_particulas)
        ]

    @property
    def duracion_total(self):
        return self.DURACION_SALIDA + self.DURACION_ENTRADA

    def _crear_sonido_sorpresa(self, tristeza=0.0):
        """Genera un efecto corto de sorpresa sin depender de un archivo.

        Con más ``tristeza`` el sobresalto suena más apagado: menos
        volumen y un tono ligeramente más grave, como un sobresalto sin
        ánimo en vez de uno alegre.
        """
        if not pygame.mixer.get_init():
            return None

        frecuencia_muestreo = 44100
        duracion = 0.38
        muestras = array("h")
        total = int(frecuencia_muestreo * duracion)
        volumen_max = 0.28 * (1.0 - tristeza * 0.45)
        factor_tono = 1.0 - tristeza * 0.25

        for indice in range(total):
            tiempo = indice / frecuencia_muestreo
            progreso = indice / total
            if progreso < 0.68:
                frecuencia = (260 + 850 * (progreso / 0.68)) * factor_tono
                volumen = min(1.0, progreso / 0.04) * (1.0 - progreso * 0.3)
            else:
                frecuencia = (920 - 520 * ((progreso - 0.68) / 0.32)) * factor_tono
                volumen = (1.0 - progreso) / 0.32

            onda = math.sin(math.tau * frecuencia * tiempo)
            golpe = math.sin(math.tau * frecuencia * 2.01 * tiempo) * 0.22
            muestra = int(32767 * volumen_max * volumen * (onda + golpe))
            muestras.append(max(-32767, min(32767, muestra)))

        return pygame.mixer.Sound(buffer=muestras.tobytes())

    @staticmethod
    def _suave(t):
        t = max(0.0, min(1.0, t))
        return t * t * (3.0 - 2.0 * t)

    @staticmethod
    def _rebote_elastico(t):
        """Easing tipo 'easeOutElastic': overshoot y resorte al asentarse,
        ideal para el squash & stretch caricaturesco de la entrada."""
        t = max(0.0, min(1.0, t))
        if t in (0.0, 1.0):
            return t
        c4 = (2 * math.pi) / 3
        return (2 ** (-10 * t)) * math.sin((t * 10 - 0.75) * c4) + 1

    @staticmethod
    def _mezclar_color(color_a, color_b, t):
        t = max(0.0, min(1.0, t))
        return tuple(int(a + (b - a) * t) for a, b in zip(color_a, color_b))

    @staticmethod
    def _generar_paleta(tono, tristeza=0.0):
        """Deriva toda la paleta de un único matiz (hue) para lograr el
        look monocromático: solo varían la saturación y el brillo.

        ``tristeza`` (0 a 1) apaga la paleta a medida que suben los
        niveles: baja la saturación (colores más grises) y el brillo
        (todo más oscuro/apagado). El rubor de las mejillas además se
        desvanece directamente, porque un personaje decaído no tiene
        las mejillas sonrosadas.
        """

        def color(saturacion, valor, alpha=255):
            saturacion *= 1.0 - tristeza * 0.6
            valor *= 1.0 - tristeza * 0.35
            r, g, b = colorsys.hsv_to_rgb(tono, saturacion, valor)
            return (int(r * 255), int(g * 255), int(b * 255), alpha)

        alpha_rubor = int(175 * (1.0 - tristeza * 0.85))
        return {
            "tinta": color(0.62, 0.16),        # contorno grueso, casi negro
            "sombra": color(0.55, 0.42, 150),  # sombra bajo la cara
            "piel": color(0.38, 0.93),         # tono principal
            "piel_luz": color(0.20, 1.0),      # zona iluminada
            "rubor": color(0.70, 0.97, alpha_rubor),  # mejillas sonrosadas
            "brillo": color(0.06, 1.0),        # brillos en ojos / nariz / dientes
            "rayo": color(0.12, 1.0, 210),     # rayos del estallido cómico
            "lengua": color(0.80, 0.55),       # franja interior de la boca (contraste)
            "pelo": color(0.60, 0.14),         # mechones de pelo, casi negro
        }

    @staticmethod
    def _bezier_cuadratica(p0, p1, p2, pasos=10):
        puntos = []
        for i in range(pasos + 1):
            t = i / pasos
            x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
            y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
            puntos.append((x, y))
        return puntos

    def progreso(self):
        """Devuelve el avance total de la transición entre 0.0 y 1.0."""
        transcurrido = pygame.time.get_ticks() - self.inicio
        return max(0.0, min(1.0, transcurrido / self.duracion_total))

    def actualizar(self, jugador):
        """Actualiza la posición y el color del jugador durante la transición.

        Returns:
            ``True`` cuando la animación terminó y el juego puede volver a
            aceptar controles.
        """
        transcurrido = pygame.time.get_ticks() - self.inicio
        if transcurrido < self.DURACION_SALIDA:
            jugador.rect.center = self.posicion_origen
            jugador.color = self.color_origen
        elif transcurrido < self.duracion_total:
            t = self._suave((transcurrido - self.DURACION_SALIDA) / self.DURACION_ENTRADA)
            punto_entrada = pygame.Vector2(self.posicion_spawn.x, -70)
            jugador.rect.center = punto_entrada.lerp(self.posicion_spawn, t)
            jugador.color = self._mezclar_color(self.color_origen, self.color_destino, t)
        else:
            jugador.rect.center = self.posicion_spawn
            jugador.color = self.color_destino
            jugador.vel_y = 0
            self.finalizada = True

        self.parpadeo = transcurrido / 130.0
        return self.finalizada

    def dibujar(self, superficie):
        """Dibuja la cortina, la cara, los rayos y las partículas animadas."""
        transcurrido = pygame.time.get_ticks() - self.inicio
        progreso = self.progreso()
        paleta = self.paleta
        tristeza = self.tristeza

        if transcurrido < self.DURACION_SALIDA:
            fase = self._suave(transcurrido / self.DURACION_SALIDA)
            intensidad = int(225 * fase)
            escala_x = 0.35 + fase * 1.15
            escala_y = 0.18 + fase * 1.05
            inclinacion = math.sin(fase * math.pi) * 10 * (1.0 - tristeza * 0.5)
            gesto = fase
        else:
            entrada = self._suave((transcurrido - self.DURACION_SALIDA) / self.DURACION_ENTRADA)
            # Con más tristeza el rebote pierde fuerza: un personaje
            # decaído "cae" en su sitio en vez de rebotar con energía.
            rebote = self._rebote_elastico(entrada) * (1.0 - tristeza * 0.55)
            intensidad = int(225 * (1.0 - entrada))
            escala_x = 0.5 + rebote * 0.9
            escala_y = 0.4 + rebote * 0.85
            inclinacion = math.sin(entrada * math.pi * 2.2) * (1.0 - entrada) * 14 * (1.0 - tristeza * 0.6)
            gesto = 1.0 - entrada

        # Cortina de color que se abre/cierra, ahora tintada con el
        # mismo matiz que la cara en vez de un azul fijo.
        capa = pygame.Surface(superficie.get_size(), pygame.SRCALPHA)
        capa.fill((*paleta["tinta"][:3], max(0, intensidad)))
        superficie.blit(capa, (0, 0))

        centro = pygame.Vector2(superficie.get_width() / 2, superficie.get_height() / 2)
        ancho = max(90, int(200 * escala_x))
        alto = max(75, int(196 * escala_y))
        margen = 56
        cara = pygame.Surface((ancho + margen * 2, alto + margen * 2), pygame.SRCALPHA)
        centro_cara = pygame.Vector2(cara.get_width() / 2, cara.get_height() / 2)

        self._dibujar_rayos(cara, centro_cara, max(ancho, alto), gesto, paleta, tristeza)
        self._dibujar_particulas(cara, centro_cara, max(ancho, alto), progreso, paleta)

        grosor = max(4, int(ancho * 0.045))

        self._dibujar_pelo(cara, centro_cara, ancho, alto, paleta, grosor)

        # Silueta con contorno grueso (look "pocket cartoon")
        pygame.draw.ellipse(
            cara, paleta["tinta"],
            (centro_cara.x - ancho / 2 - grosor, centro_cara.y - alto / 2 - grosor,
             ancho + grosor * 2, alto + grosor * 2),
        )
        pygame.draw.ellipse(
            cara, paleta["sombra"],
            (centro_cara.x - ancho / 2 + 8, centro_cara.y - alto / 2 + 14, ancho, alto),
        )
        pygame.draw.ellipse(
            cara, paleta["piel"],
            (centro_cara.x - ancho / 2, centro_cara.y - alto / 2, ancho, alto),
        )
        pygame.draw.ellipse(
            cara, paleta["piel_luz"],
            (centro_cara.x - ancho * 0.38, centro_cara.y - alto * 0.42, ancho * 0.55, alto * 0.5),
        )

        self._dibujar_cejas(cara, centro_cara, ancho, alto, gesto, paleta, grosor, tristeza)
        self._dibujar_ojos(cara, centro_cara, ancho, alto, gesto, paleta, grosor, tristeza)
        self._dibujar_nariz(cara, centro_cara, ancho, alto, paleta, grosor)
        self._dibujar_boca(cara, centro_cara, ancho, alto, gesto, paleta, grosor, tristeza)
        self._dibujar_lagrima(cara, centro_cara, ancho, alto, paleta, tristeza)

        # Un personaje decaído deja caer un poco la cabeza.
        cara_rotada = pygame.transform.rotate(cara, inclinacion)
        destino = centro - pygame.Vector2(cara_rotada.get_width() / 2, cara_rotada.get_height() / 2)
        destino.y += tristeza * alto * 0.08
        superficie.blit(cara_rotada, destino)

    def _dibujar_rayos(self, superficie, centro, radio_base, gesto, paleta, tristeza=0.0):
        gesto = max(0.0, min(1.0, gesto))
        if gesto <= 0.02:
            return
        # Con mucha tristeza el chispazo cómico se apaga: menos rayos,
        # más cortos y finos, como un sobresalto sin alegría.
        num_rayos = max(3, int(self.NUM_RAYOS * (1.0 - tristeza * 0.7)))
        largo = radio_base * (0.55 + gesto * 0.65) * (1.0 - tristeza * 0.5)
        grosor = max(2, int(radio_base * 0.035 * gesto * (1.0 - tristeza * 0.4)))
        for i in range(num_rayos):
            angulo = (math.tau / num_rayos) * i
            direccion = pygame.Vector2(math.cos(angulo), math.sin(angulo))
            interior = centro + direccion * (radio_base * 0.55)
            exterior = centro + direccion * (radio_base * 0.55 + largo)
            pygame.draw.line(superficie, paleta["rayo"], interior, exterior, grosor)

    def _dibujar_particulas(self, superficie, centro, radio_base, progreso, paleta):
        empuje = self._suave(min(1.0, progreso * 1.6))
        desvanecimiento = 1.0 - self._suave(max(0.0, (progreso - 0.5) * 2.0))
        alpha = int(220 * desvanecimiento)
        if alpha <= 0:
            return
        for angulo, distancia, tamano in self._particulas:
            radio = radio_base * (0.5 + distancia * empuje * 0.9)
            pos = centro + pygame.Vector2(math.cos(angulo), math.sin(angulo)) * radio
            pygame.draw.circle(
                superficie, (*paleta["brillo"][:3], alpha), pos, max(1.5, tamano * (0.4 + empuje * 0.6))
            )

    def _dibujar_pelo(self, superficie, centro, ancho, alto, paleta, grosor):
        # Un par de mechones puntiagudos asomando arriba de la cabeza,
        # como el pelo alborotado que se le escapa a los personajes de
        # Maddocks por debajo del sombrero.
        base_y = centro.y - alto * 0.42
        posiciones = (-0.22, 0.0, 0.22)
        largos = (0.16, 0.24, 0.14)
        for offset, largo in zip(posiciones, largos):
            bx = centro.x + ancho * offset
            p0 = (bx - ancho * 0.05, base_y)
            p1 = (bx + ancho * offset * 0.4, base_y - alto * largo)
            p2 = (bx + ancho * 0.05, base_y)
            pygame.draw.polygon(superficie, paleta["tinta"], [p0, p1, p2])
            interior = [
                (bx - ancho * 0.02, base_y - alto * 0.01),
                (bx + ancho * offset * 0.4, base_y - alto * largo * 0.82),
                (bx + ancho * 0.02, base_y - alto * 0.01),
            ]
            pygame.draw.polygon(superficie, paleta["pelo"], interior)

    def _dibujar_cejas(self, superficie, centro, ancho, alto, gesto, paleta, grosor, tristeza=0.0):
        # Cejas finas y muy arqueadas, bien separadas de los ojos: el
        # trazo suelto y "en acento circunflejo" típico de Peter
        # Maddocks, no una ceja gruesa pegada al ojo.
        #
        # Con tristeza, el arco se va invirtiendo hacia la clásica ceja
        # de preocupación/tristeza: la punta interior (junto a la nariz)
        # sube y la punta exterior baja, aplanando el arco alegre.
        separacion = ancho * 0.26
        y = centro.y - alto * 0.30 - gesto * alto * 0.06
        largo = ancho * 0.24
        # Un arco más contenido (antes llegaba a 1.1x): con gesto=1 el
        # arco original formaba un pico puntiagudo en vez de una ceja
        # arqueada, que es justo el instante de mayor sorpresa y donde
        # más se notaba lo "raro" del gesto.
        arco = largo * (0.45 + gesto * 0.35) * (1.0 - tristeza * 0.55)
        inclinacion_triste = tristeza * largo * 0.30
        grosor_ceja = max(4, int(grosor * 0.75))
        for lado in (-1, 1):
            # Ligera asimetría entre cejas para que no se vea calcado,
            # pero moderada para no rozar el "ojo bizco" en el pico del gesto.
            asimetria = 1.0 if lado < 0 else 1.06
            x = centro.x + lado * separacion
            p0 = (x - lado * largo / 2, y + arco * 0.30 - inclinacion_triste)
            p1 = (x + lado * largo * 0.05, y - arco * asimetria)
            p2 = (x + lado * largo * 0.75, y - arco * 0.10 + inclinacion_triste)
            puntos = self._bezier_cuadratica(p0, p1, p2, pasos=8)
            pygame.draw.lines(superficie, paleta["tinta"], False, puntos, grosor_ceja)

    def _dibujar_ojos(self, superficie, centro, ancho, alto, gesto, paleta, grosor, tristeza=0.0):
        # Ojos enormes, muy redondos y ligeramente asimétricos (uno un
        # poco más grande que el otro), con pupila grande y central: la
        # mirada bien abierta y algo boba de los personajes de Maddocks.
        # El parpadeo se desactiva cerca del pico del gesto: parpadear
        # justo en el instante de mayor sorpresa se veía como un glitch
        # (ojos cerrados sobre una boca de shock bien abierta).
        ojo_cerrado = math.sin(self.parpadeo) > 0.86 and gesto < 0.4
        y = centro.y - alto * 0.16 + tristeza * alto * 0.03
        separacion = ancho * 0.25
        radio_base = max(13, ancho * 0.165)
        for lado in (-1, 1):
            x = centro.x + lado * separacion
            radio = radio_base * (0.92 if lado < 0 else 1.0)
            if ojo_cerrado:
                pygame.draw.line(
                    superficie, paleta["tinta"],
                    (x - radio, y), (x + radio, y),
                    max(3, int(grosor * 0.85)),
                )
                continue
            pygame.draw.circle(superficie, paleta["tinta"], (x, y), radio + max(3, int(grosor * 0.45)))
            pygame.draw.circle(superficie, (255, 255, 255, 255), (x, y), radio)
            # La mirada baja y se apaga con la tristeza: la pupila se
            # desplaza hacia abajo en vez de mirar al frente, y los
            # brillos se achican (ojo apagado, sin chispa).
            pupila = pygame.Vector2(
                x + lado * radio * 0.06,
                y - radio * 0.06 + radio * tristeza * 0.45,
            )
            pygame.draw.circle(superficie, paleta["tinta"], pupila, radio * 0.56)
            brillo = pupila + pygame.Vector2(-radio * 0.22, -radio * 0.24)
            pygame.draw.circle(superficie, paleta["brillo"], brillo, max(2, radio * (0.24 - tristeza * 0.14)))
            brillo_chico = pupila + pygame.Vector2(radio * 0.28, radio * 0.20)
            pygame.draw.circle(superficie, paleta["brillo"], brillo_chico, max(1.5, radio * (0.10 - tristeza * 0.06)))

            if tristeza > 0.05:
                # Párpado caído: una porción del color de piel tapa la
                # parte superior del ojo, como el ojo entrecerrado y
                # pesado de alguien decaído.
                alto_parpado = radio * 1.2 * tristeza
                borde_superior = y - radio - max(3, int(grosor * 0.45))
                parpado = pygame.Rect(0, 0, radio * 2.3, alto_parpado)
                parpado.midtop = (x, borde_superior)
                pygame.draw.ellipse(superficie, paleta["tinta"], parpado)
                relleno = pygame.Rect(0, 0, radio * 2.0, max(0, alto_parpado - grosor * 0.6))
                relleno.midtop = (x, borde_superior + grosor * 0.35)
                pygame.draw.ellipse(superficie, paleta["piel"], relleno)

    def _dibujar_nariz(self, superficie, centro, ancho, alto, paleta, grosor):
        # Nariz larga y redondeada, con un ligero gancho hacia un lado:
        # rasgo protagonista en los rostros de Peter Maddocks, no un
        # simple punto. Baja desde el entrecejo casi hasta la sonrisa.
        y_arriba = centro.y - alto * 0.10
        y_abajo = centro.y + alto * 0.05
        gancho = ancho * 0.05

        p0 = (centro.x - ancho * 0.015, y_arriba)
        p1 = (centro.x + gancho, centro.y + alto * 0.08)
        p2 = (centro.x + gancho * 0.6, y_abajo)
        puntos = self._bezier_cuadratica(p0, p1, p2, pasos=10)

        grosor_nariz = max(6, int(ancho * 0.055))
        pygame.draw.lines(superficie, paleta["tinta"], False, puntos, grosor_nariz + max(2, int(grosor * 0.4)))
        pygame.draw.lines(superficie, paleta["sombra"], False, puntos, grosor_nariz)

        # Bulbo redondeado en la punta, con su propio brillo.
        punta = pygame.Vector2(p2)
        radio_bulbo = max(5, ancho * 0.045)
        pygame.draw.circle(superficie, paleta["tinta"], punta, radio_bulbo + max(2, int(grosor * 0.35)))
        pygame.draw.circle(superficie, paleta["rubor"], punta, radio_bulbo)
        brillo = punta + pygame.Vector2(-radio_bulbo * 0.35, -radio_bulbo * 0.4)
        pygame.draw.circle(superficie, paleta["brillo"], brillo, max(1.5, radio_bulbo * 0.32))

    def _dibujar_mejillas(self, superficie, centro, ancho, alto, paleta):
        for lado in (-1, 1):
            x = centro.x + lado * ancho * 0.34
            y = centro.y + alto * 0.14
            pygame.draw.ellipse(
                superficie, paleta["rubor"],
                (x - ancho * 0.10, y - alto * 0.06, ancho * 0.20, alto * 0.12),
            )

    def _dibujar_boca(self, superficie, centro, ancho, alto, gesto, paleta, grosor, tristeza=0.0):
        """Boca única que se transforma sin cortes entre la "O" de sorpresa
        y la sonrisa amplia, según ``gesto`` (1 = sorpresa, 0 = sonrisa).

        Antes había dos dibujos completamente distintos que se
        intercambiaban de golpe justo en el pico del gesto (el instante de
        mayor sorpresa), lo que se veía como un salto brusco. Ahora es una
        sola forma que interpola tamaño, color de la cavidad y la
        aparición gradual de dientes/lengua, así el gesto fluye en vez de
        "saltar".

        ``tristeza`` reparte la posición de reposo (``gesto`` = 0) entre
        una sonrisa amplia con dientes (alegre) y un pequeño puchero con
        las comisuras hacia abajo (triste); la "O" de sorpresa se
        mantiene igual en ambos casos, porque un sobresalto se ve igual
        sea cual sea el humor del personaje.
        """
        apertura = max(0.0, min(1.0, gesto))
        factor_sonrisa = 1.0 - apertura
        factor_alegre = factor_sonrisa * (1.0 - tristeza)
        factor_triste = factor_sonrisa * tristeza
        x = centro.x
        y = centro.y + alto * (0.30 + apertura * 0.02)

        radio_o = max(7, ancho * 0.11)
        # La boca cerrada de reposo es ancha si es sonrisa y chica/apretada
        # si es puchero; la "O" de sorpresa no cambia con la tristeza.
        ancho_boca = ancho * (0.74 * factor_alegre + 0.40 * factor_triste) + radio_o * 2 * apertura
        alto_boca = alto * (0.42 * factor_alegre + 0.16 * factor_triste) + radio_o * 2 * apertura

        contorno = pygame.Rect(0, 0, ancho_boca + grosor * 1.8, alto_boca + grosor * 1.8)
        contorno.center = (x, y)
        pygame.draw.ellipse(superficie, paleta["tinta"], contorno)

        # La cavidad pasa de un tono lengua (boca "O") a un fondo oscuro
        # (boca sonriente, donde lo que se ve son los dientes de encima).
        cavidad = pygame.Rect(0, 0, ancho_boca, alto_boca)
        cavidad.center = (x, y)
        color_cavidad = self._mezclar_color(paleta["tinta"][:3], paleta["lengua"][:3], apertura)
        pygame.draw.ellipse(superficie, color_cavidad, cavidad)

        # Dientes y franja de encía/lengua: se desvanecen a medida que la
        # boca se cierra hacia la "O" o hacia el puchero triste, en vez de
        # aparecer o desaparecer de golpe.
        if factor_alegre > 0.03:
            alpha = int(255 * min(1.0, factor_alegre * 1.3))

            franja = pygame.Rect(0, 0, ancho_boca * 0.94, alto_boca * 0.55)
            franja.center = (x, y + alto_boca * 0.16)
            pygame.draw.ellipse(superficie, (*paleta["lengua"][:3], alpha), franja)

            dientes = pygame.Rect(0, 0, ancho_boca * 0.86, alto_boca * 0.50)
            dientes.center = (x, y - alto_boca * 0.20)
            radio_esquina = max(1, int(dientes.height * 0.35))
            pygame.draw.rect(superficie, (*paleta["brillo"][:3], alpha), dientes, border_radius=radio_esquina)
            pygame.draw.rect(
                superficie, (*paleta["tinta"][:3], alpha), dientes,
                max(2, int(grosor * 0.3)), border_radius=radio_esquina,
            )
            divisiones = 7
            for i in range(1, divisiones):
                lx = dientes.left + dientes.width * i / divisiones
                pygame.draw.line(
                    superficie, (*paleta["tinta"][:3], alpha),
                    (lx, dientes.top + 2), (lx, dientes.bottom - 2),
                    max(1, int(grosor * 0.22)),
                )

        if factor_triste > 0.03:
            # Comisuras hacia abajo por encima de la boca cerrada: el
            # clásico puchero de tristeza, dibujado con la misma técnica
            # de curva Bézier que las cejas.
            alpha_triste = int(255 * min(1.0, factor_triste * 1.4))
            ancho_puchero = ancho_boca * 0.85
            caida = alto_boca * 0.55
            p0 = (x - ancho_puchero / 2, y + caida)
            p1 = (x, y - alto_boca * 0.10)
            p2 = (x + ancho_puchero / 2, y + caida)
            puntos = self._bezier_cuadratica(p0, p1, p2, pasos=10)
            grosor_puchero = max(2, int(grosor * 0.55))
            color_puchero = (*paleta["tinta"][:3], alpha_triste)
            pygame.draw.lines(superficie, color_puchero, False, puntos, grosor_puchero)
     
    def _dibujar_lagrima(self, superficie, centro, ancho, alto, paleta, tristeza):
        """Una lagrimita que solo aparece en los niveles más tristes
        (tristeza > 0.6), como remate del gesto decaído."""
        aparicion = max(0.0, min(1.0, (tristeza - 0.6) / 0.4))
        if aparicion <= 0.0:
            return
        x = centro.x + ancho * 0.25
        y_inicio = centro.y - alto * 0.02
        largo = alto * (0.16 + 0.10 * aparicion)
        ancho_lagrima = max(3, ancho * 0.045)
        y_fin = y_inicio + largo * aparicion
        alpha = int(220 * aparicion)
        color = (*paleta["brillo"][:3], alpha)
        punta = (x, y_inicio)
        base_izq = (x - ancho_lagrima, y_fin - ancho_lagrima * 0.4)
        base_der = (x + ancho_lagrima, y_fin - ancho_lagrima * 0.4)
        pygame.draw.polygon(superficie, color, [punta, base_izq, base_der])
        pygame.draw.circle(superficie, color, (x, y_fin), ancho_lagrima)