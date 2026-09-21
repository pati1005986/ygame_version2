"""Transición caricaturesca entre niveles, sin imágenes ni archivos de audio.

La clase pública ``TransicionCaricaturesca`` se actualiza desde el bucle del
juego y se dibuja encima del nivel. También sintetiza y reproduce un efecto
de "boing" de sorpresa al comenzar cada transición.

Qué hace que se vea dibujada a mano y natural (en vez de "figuras de Pygame"):

* **Supersampling**: la cara se pinta al doble de resolución y se reduce con
  suavizado, así no hay bordes dentados. El giro usa ``rotozoom`` (suave).
* **Trazo de tinta**: cejas, nariz, pelo y ceño se dibujan como pinceladas
  con extremos redondeados y grosor variable, no como líneas uniformes.
* **Contorno tembloroso ("line boil")**: el borde de la cabeza cambia
  ligeramente unas 11 veces por segundo, como en la animación dibujada a mano.
* **Principios de animación**: anticipación, sobreimpulso, *squash & stretch*
  que conserva el volumen, resorte amortiguado, pausa en el susto y
  movimiento secundario (el pelo se retrasa respecto a la cabeza).
* **Detalles con personalidad**: los ojos siguen al jugador, las pupilas se
  encogen con el susto, el parpadeo es a destiempo y con párpado, gotas de
  sudor y un estallido irregular detrás de la cabeza.
* **Iris de cierre** al estilo dibujos clásicos, y el jugador aterriza con
  rebotes en vez de deslizarse.
"""

import colorsys
import math
import random
from array import array

import pygame

# Tamaño lógico de la cara. Todo se dibuja en estas unidades y luego se
# escala, así el squash & stretch deforma también ojos, boca y nariz.
_ANCHO = 200.0
_ALTO = 196.0
_MARGEN = 90.0  # espacio libre alrededor (pelo, gotas de sudor)
_LIENZO_ANCHO = _ANCHO + 2 * _MARGEN
_LIENZO_ALTO = _ALTO + 2 * _MARGEN
_RADIO_ESTALLIDO = 260.0


def _limitar(valor, minimo=0.0, maximo=1.0):
    return max(minimo, min(maximo, valor))


class _Lienzo:
    """Superficie de trabajo con supersampling.

    Se dibuja en unidades lógicas; internamente todo se multiplica por
    ``ss`` y al final ``reducir`` devuelve la imagen suavizada. Las
    funciones de ``pygame.draw`` no mezclan alfa sobre superficies
    ``SRCALPHA`` (lo sobrescriben), por eso aquí todo se pinta opaco y las
    transparencias se resuelven mezclando colores.
    """

    def __init__(self, ancho, alto, ss):
        self.ss = ss
        self.superficie = pygame.Surface((int(ancho * ss), int(alto * ss)), pygame.SRCALPHA)

    def limpiar(self, color):
        # Se rellena con el color de la tinta (alfa 0): así los bordes
        # suavizados al reducir se mezclan con tinta y no con negro puro.
        self.superficie.fill((*color[:3], 0))

    def elipse(self, color, centro, ancho, alto):
        ss = self.ss
        w, h = round(ancho * ss), round(alto * ss)
        if w < 1 or h < 1:
            return
        rect = pygame.Rect(0, 0, w, h)
        rect.center = (round(centro[0] * ss), round(centro[1] * ss))
        pygame.draw.ellipse(self.superficie, (*color[:3], 255), rect)

    def circulo(self, color, centro, radio):
        ss = self.ss
        if radio * ss < 0.5:
            return
        pygame.draw.circle(self.superficie, (*color[:3], 255), (centro[0] * ss, centro[1] * ss), radio * ss)

    def poligono(self, color, puntos):
        if len(puntos) < 3:
            return
        ss = self.ss
        pygame.draw.polygon(self.superficie, (*color[:3], 255), [(x * ss, y * ss) for x, y in puntos])

    def trazo(self, color, puntos, grosor_ini, grosor_fin=None, panza=0.0):
        """Pincelada con extremos redondeados y grosor variable.

        ``grosor_ini``/``grosor_fin`` son los diámetros en cada punta y
        ``panza`` engorda el centro (0.5 = un 50 % más grueso a mitad).
        """
        if grosor_fin is None:
            grosor_fin = grosor_ini
        tramos = list(zip(puntos[:-1], puntos[1:]))
        largos = [math.dist(a, b) for a, b in tramos]
        total = sum(largos) or 1.0
        paso = max(0.9, min(grosor_ini, grosor_fin) * 0.3)
        muestras = []
        recorrido = 0.0
        for (a, b), largo in zip(tramos, largos):
            n = max(1, int(largo / paso))
            for i in range(n):
                f = i / n
                muestras.append(
                    ((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f), (recorrido + largo * f) / total)
                )
            recorrido += largo
        muestras.append((tuple(puntos[-1]), 1.0))
        for punto, t in muestras:
            grosor = (grosor_ini + (grosor_fin - grosor_ini) * t) * (1.0 + panza * math.sin(math.pi * t))
            self.circulo(color, punto, grosor / 2)

    def reducir(self, tamano):
        return pygame.transform.smoothscale(self.superficie, tamano)


class TransicionCaricaturesca:
    """Transición de nivel con una cara caricaturesca dibujada con Pygame.

    El diseño se inspira en el trazo grueso y gestual de los "pocket
    cartoons" británicos (línea negra marcada, rasgos muy exagerados,
    pocos colores). Cada transición elige al azar un único matiz y toda
    la cara se pinta en variaciones de ese mismo color (look
    monocromático), así nunca se repite la misma combinación dos veces.

    Línea de tiempo (los valores se pueden ajustar con las constantes):

    * Salida: la cara "salta" con anticipación y sobreimpulso mientras el
      iris se cierra; el susto llega a su punto máximo.
    * Entrada: la cara se queda pasmada un instante, tiembla, rebota como
      un resorte, se relaja en una sonrisa, parpadea y se desinfla mientras
      el iris se abre y el jugador cae y rebota en su sitio.
    """

    DURACION_SALIDA = 380
    DURACION_ENTRADA = 680

    NUM_PUNTAS = 9  # puntas del estallido detrás de la cabeza
    ESCALA_CARA = 1.3  # tamaño de la cara en reposo (1.0 = 200 px de ancho)
    ESCALA_ESTALLIDO = 1.75  # radio del estallido, en radios de cabeza
    SUPERMUESTREO = 2  # 1 = sin suavizado (más rápido), 2 = recomendado
    USAR_IRIS = True  # False = cortina de color que se desvanece
    ALFA_CORTINA = 225

    # Empieza a decaerse a partir del nivel 10 y alcanza el máximo
    # alrededor del nivel 18. Ajusta estos valores si cambias la curva
    # de progresión del juego.
    NIVEL_INICIO_TRISTEZA = 10
    NIVEL_TRISTEZA_MAXIMA = 18

    def __init__(
        self,
        color_origen,
        color_destino,
        posicion_origen,
        posicion_spawn,
        nivel=0,
        volumen_efectos=1.0,
    ):
        self.color_origen = color_origen
        self.color_destino = color_destino
        self.posicion_origen = pygame.Vector2(posicion_origen)
        self.posicion_spawn = pygame.Vector2(posicion_spawn)
        self.finalizada = False
        self.volumen_efectos = _limitar(float(volumen_efectos))

        # A medida que sube el nivel, la cara se pone más triste/decaída:
        # cejas preocupadas, mirada caída, boca hacia abajo, colores
        # apagados y menos "chispa" en la animación.
        # 0.0 = expresión feliz/sorprendida normal, 1.0 = muy triste.
        self.nivel = nivel
        if nivel < self.NIVEL_INICIO_TRISTEZA:
            self.tristeza = 0.0
        else:
            rango = max(1, self.NIVEL_TRISTEZA_MAXIMA - self.NIVEL_INICIO_TRISTEZA)
            self.tristeza = _limitar((nivel - self.NIVEL_INICIO_TRISTEZA) / rango)

        # Un matiz aleatorio distinto en cada transición; toda la cara
        # se deriva de él (solo cambian saturación y brillo, y además se
        # apagan un poco según la tristeza).
        self.tono = random.random()
        self.paleta = self._generar_paleta(self.tono, self.tristeza)

        # Todo lo aleatorio se decide una sola vez para que no titile de
        # un fotograma a otro.
        self._lienzo = _Lienzo(_LIENZO_ANCHO, _LIENZO_ALTO, self.SUPERMUESTREO)
        self._centro_lienzo = pygame.Vector2(_LIENZO_ANCHO / 2, _LIENZO_ALTO / 2)
        # Variantes del contorno tembloroso: se alternan unas 11 veces/s.
        self._boil = [tuple(random.uniform(0, math.tau) for _ in range(3)) for _ in range(5)]
        # Un único parpadeo, a media entrada y con algo de azar.
        self._t_parpadeo = self.DURACION_SALIDA + self.DURACION_ENTRADA * random.uniform(0.38, 0.52)
        # Gotas de sudor: (lado, vel. horizontal, vel. vertical, retraso, tamaño).
        self._gotas = [
            (-1, 80.0, -150.0, 0.00, 1.00),
            (1, 95.0, -130.0, 0.06, 1.15),
            (1, 55.0, -175.0, 0.14, 0.75),
        ]
        self._estallido = self._crear_estallido()
        self._capa = None
        self._pos_jugador = pygame.Vector2(posicion_origen)
        self._mirada = pygame.Vector2(0, 0)

        self.sonido_sorpresa = self._crear_sonido_sorpresa(self.tristeza)
        # El reloj arranca al final: crear el sonido y el estallido tarda
        # unos milisegundos y no queremos "comernos" el inicio de la animación.
        self.inicio = pygame.time.get_ticks()
        if self.sonido_sorpresa:
            self.sonido_sorpresa.set_volume(self.volumen_efectos)
            self.sonido_sorpresa.play()

    @property
    def duracion_total(self):
        return self.DURACION_SALIDA + self.DURACION_ENTRADA

    # ------------------------------------------------------------------
    # Sonido
    # ------------------------------------------------------------------
    def _crear_sonido_sorpresa(self, tristeza=0.0):
        """Genera un "boing" corto de sorpresa sin depender de un archivo.

        Con más ``tristeza`` suena más apagado: menos volumen y un tono
        ligeramente más grave, como un sobresalto sin ánimo.

        Se adapta al mezclador activo (frecuencia y canales); si el formato
        no es de 16 bits con signo devuelve ``None`` en vez de sonar mal.
        """
        if not pygame.mixer.get_init():
            return None
        frecuencia_muestreo, formato, canales = pygame.mixer.get_init()
        if formato != -16:
            return None

        duracion = 0.42
        total = int(frecuencia_muestreo * duracion)
        volumen_max = 0.30 * (1.0 - tristeza * 0.45)
        factor_tono = 1.0 - tristeza * 0.25
        muestras = array("h")
        fase = 0.0

        for indice in range(total):
            tiempo = indice / frecuencia_muestreo
            progreso = indice / total
            # Sube rápido y cae más despacio (continuo en el punto de giro).
            if progreso < 0.62:
                base = 260 + 900 * (progreso / 0.62) ** 0.8
            else:
                base = 1160 - 780 * ((progreso - 0.62) / 0.38) ** 1.2
            # Vibrato de resorte que se va apagando.
            vibrato = 1.0 + 0.045 * math.sin(math.tau * 22 * tiempo) * (1.0 - progreso * 0.6)
            frecuencia = base * vibrato * factor_tono
            # Se acumula la fase: así el barrido de frecuencia es limpio.
            fase += math.tau * frecuencia / frecuencia_muestreo
            envolvente = min(1.0, progreso / 0.03) * (1.0 - progreso) ** 0.7
            onda = math.sin(fase) + 0.22 * math.sin(fase * 2.01)
            muestra = int(32767 * volumen_max * envolvente * onda)
            muestra = max(-32767, min(32767, muestra))
            for _ in range(canales):
                muestras.append(muestra)

        return pygame.mixer.Sound(buffer=muestras.tobytes())

    # ------------------------------------------------------------------
    # Utilidades de easing y color
    # ------------------------------------------------------------------
    @staticmethod
    def _suave(t):
        t = _limitar(t)
        return t * t * (3.0 - 2.0 * t)

    @staticmethod
    def _sale_atras(t, c1=1.70158):
        """easeOutBack: llega, se pasa un poco y vuelve (sobreimpulso)."""
        t = _limitar(t)
        c3 = c1 + 1.0
        return 1.0 + c3 * (t - 1.0) ** 3 + c1 * (t - 1.0) ** 2

    @staticmethod
    def _entra_atras(t, c1=1.70158):
        """easeInBack: primero "toma impulso" hacia atrás y luego se lanza."""
        t = _limitar(t)
        c3 = c1 + 1.0
        return c3 * t ** 3 - c1 * t ** 2

    @staticmethod
    def _rebote_suelo(t):
        """easeOutBounce: cae con la gravedad y rebota al llegar al suelo."""
        t = _limitar(t)
        n1, d1 = 7.5625, 2.75
        if t < 1 / d1:
            return n1 * t * t
        if t < 2 / d1:
            t -= 1.5 / d1
            return n1 * t * t + 0.75
        if t < 2.5 / d1:
            t -= 2.25 / d1
            return n1 * t * t + 0.9375
        t -= 2.625 / d1
        return n1 * t * t + 0.984375

    @staticmethod
    def _mezclar_color(color_a, color_b, t):
        t = _limitar(t)
        return tuple(int(a + (b - a) * t) for a, b in zip(color_a[:3], color_b[:3]))

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
            "sombra": color(0.55, 0.42, 150),  # sombreado bajo la cara
            "piel": color(0.38, 0.93),         # tono principal
            "piel_luz": color(0.20, 1.0),      # zona iluminada
            "rubor": color(0.70, 0.97, alpha_rubor),  # mejillas sonrosadas
            "brillo": color(0.06, 1.0),        # brillos en ojos / nariz / dientes
            "rayo": color(0.12, 1.0, 210),     # estallido cómico
            "lengua": color(0.80, 0.55),       # interior de la boca (contraste)
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

    # ------------------------------------------------------------------
    # Línea de tiempo
    # ------------------------------------------------------------------
    def progreso(self):
        """Devuelve el avance total de la transición entre 0.0 y 1.0."""
        transcurrido = pygame.time.get_ticks() - self.inicio
        return _limitar(transcurrido / self.duracion_total)

    def _estado(self, ms):
        """Estado de la animación en el instante ``ms`` (desde el inicio).

        Es una función pura del tiempo: así se puede evaluar también un
        instante anterior para saber la *velocidad* y animar el pelo.

        * ``escala``: tamaño general de la cara (0 = invisible).
        * ``estirar``: >0 estira en vertical, <0 aplasta. Conserva el
          volumen: el ancho se reduce lo mismo que crece el alto.
        * ``gesto``: 1 = sorpresa, 0 = sonrisa (o puchero si hay tristeza).
        * ``inclinacion``: grados de giro de la cabeza.
        * ``iris``: 1 = abierto (nivel visible), 0 = cerrado del todo.
        * ``temblor``: intensidad del temblor de susto (0 a 1).
        """
        tri = self.tristeza
        if ms < self.DURACION_SALIDA:
            u = ms / self.DURACION_SALIDA
            return {
                # Salta con sobreimpulso; con tristeza el impulso es menor.
                "escala": self.ESCALA_CARA * self._sale_atras(u, 2.6 * (1.0 - tri * 0.6)),
                # Nace estirada hacia arriba y se relaja.
                "estirar": 0.30 * (1.0 - u) ** 2 * (1.0 - tri * 0.5),
                "gesto": self._suave(u),
                "inclinacion": math.sin(u * math.pi) * 9.0 * (1.0 - tri * 0.5),
                "iris": 1.0 - self._suave(u),
                "temblor": 0.0,
            }

        v = min(1.0, (ms - self.DURACION_SALIDA) / self.DURACION_ENTRADA)
        entrada = self._suave(v)
        # Resorte amortiguado: aplasta, estira, aplasta... cada vez menos.
        # Con tristeza el rebote pierde fuerza: "cae" en su sitio.
        resorte = math.exp(-5.0 * v) * math.sin(math.tau * 2.2 * v)
        # Al final se desinfla: primero toma un poco de impulso (crece un
        # pelín) y luego se encoge hasta desaparecer.
        salida = (v - 0.62) / 0.38
        return {
            "escala": self.ESCALA_CARA * (1.0 - self._entra_atras(salida, 1.9 * (1.0 - tri * 0.8))),
            "estirar": 0.32 * resorte * (1.0 - tri * 0.55),
            # Se queda pasmada un instante antes de relajar el gesto.
            "gesto": 1.0 - self._suave((v - 0.10) / 0.45),
            "inclinacion": math.sin(entrada * math.pi * 2.2) * (1.0 - entrada) * 14.0 * (1.0 - tri * 0.6),
            "iris": self._suave((v - 0.06) / 0.74),
            "temblor": max(0.0, 1.0 - v / 0.30),
        }

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
            v = (transcurrido - self.DURACION_SALIDA) / self.DURACION_ENTRADA
            # Cae desde arriba con gravedad y rebota al aterrizar.
            caida = _limitar((v - 0.10) / 0.75)
            y_inicio = -70.0
            y = y_inicio + (self.posicion_spawn.y - y_inicio) * self._rebote_suelo(caida)
            jugador.rect.center = (self.posicion_spawn.x, y)
            jugador.color = self._mezclar_color(self.color_origen, self.color_destino, self._suave(v))
        else:
            jugador.rect.center = self.posicion_spawn
            jugador.color = self.color_destino
            jugador.vel_y = 0
            self.finalizada = True

        # La cara mira al jugador (ver ``_actualizar_mirada``).
        self._pos_jugador = pygame.Vector2(jugador.rect.center)
        return self.finalizada

    # ------------------------------------------------------------------
    # Dibujo general
    # ------------------------------------------------------------------
    def dibujar(self, superficie):
        """Dibuja el iris, el estallido y la cara animada."""
        ms = pygame.time.get_ticks() - self.inicio
        estado = self._estado(ms)
        centro = pygame.Vector2(superficie.get_width() / 2, superficie.get_height() / 2)

        self._dibujar_cortina(superficie, centro, estado["iris"])
        if estado["escala"] < 0.03:
            return

        self._actualizar_mirada(centro)
        self._dibujar_estallido(superficie, centro, estado, ms)

        anterior = self._estado(max(0, ms - 45))
        self._pintar_cara(ms, estado, anterior)

        # Squash & stretch: el volumen se conserva (ancho * alto constante).
        k = max(0.6, 1.0 + estado["estirar"])
        sx = estado["escala"] / k
        sy = estado["escala"] * k
        tamano = (max(1, round(_LIENZO_ANCHO * sx)), max(1, round(_LIENZO_ALTO * sy)))
        cara = self._lienzo.reducir(tamano)
        if abs(estado["inclinacion"]) > 0.25:
            cara = pygame.transform.rotozoom(cara, estado["inclinacion"], 1.0)

        tri = self.tristeza
        # Temblor de susto (pequeño, rápido y que se apaga).
        intensidad = estado["temblor"] * (1.0 - tri * 0.5)
        tx = math.sin(ms * 0.11) * 3.0 * intensidad
        ty = math.cos(ms * 0.13) * 2.0 * intensidad
        # Al estirarse la cara "se apoya" en su base en vez de crecer desde
        # el centro (60 %), y un personaje decaído deja caer la cabeza.
        apoyo = (estado["escala"] - sy) * _ALTO * 0.5 * 0.6
        caida_cabeza = tri * _ALTO * estado["escala"] * 0.06
        destino = pygame.Vector2(
            centro.x + tx - cara.get_width() / 2,
            centro.y + ty + apoyo + caida_cabeza - cara.get_height() / 2,
        )
        superficie.blit(cara, destino)

    def _actualizar_mirada(self, centro):
        """La cara sigue con los ojos al jugador (con un poco de retraso)."""
        objetivo = self._pos_jugador - centro
        distancia = objetivo.length()
        if distancia > 1.0:
            objetivo = objetivo / distancia * min(1.0, distancia / 260.0)
        else:
            objetivo = pygame.Vector2(0, 0)
        self._mirada = self._mirada.lerp(objetivo, 0.3)

    def _dibujar_cortina(self, superficie, centro, iris):
        """Iris que se cierra sobre la cara y se abre para revelar el nivel."""
        if iris >= 0.999:
            return
        ancho, alto = superficie.get_size()
        color = self.paleta["tinta"][:3]
        if self._capa is None or self._capa.get_size() != (ancho, alto):
            self._capa = pygame.Surface((ancho, alto), pygame.SRCALPHA)

        if not self.USAR_IRIS or iris <= 0.0:
            alfa = self.ALFA_CORTINA if self.USAR_IRIS else int(self.ALFA_CORTINA * (1.0 - iris))
            if alfa > 0:
                self._capa.fill((*color, alfa))
                superficie.blit(self._capa, (0, 0))
            return

        radio = math.hypot(ancho, alto) / 2 * iris
        capa = self._capa
        capa.fill((*color, self.ALFA_CORTINA))
        # Borde difuminado de ~4 px: círculos concéntricos cuya opacidad
        # baja hacia el centro (``draw`` no suaviza, esto lo disimula).
        for desfase, fraccion in ((3, 0.85), (2, 0.65), (1, 0.45), (0, 0.22), (-1, 0.0)):
            if radio + desfase >= 1.0:
                pygame.draw.circle(
                    capa, (*color, int(self.ALFA_CORTINA * fraccion)), (centro.x, centro.y), radio + desfase
                )
        superficie.blit(capa, (0, 0))

    # ------------------------------------------------------------------
    # Estallido detrás de la cabeza
    # ------------------------------------------------------------------
    def _crear_estallido(self):
        """Estrella irregular con contorno de tinta, pintada una sola vez.

        Después solo se gira y escala (``rotozoom``) en cada fotograma.
        Con tristeza tiene menos puntas: un sobresalto sin alegría.
        """
        paleta = self.paleta
        puntas = max(6, round(self.NUM_PUNTAS * (1.0 - self.tristeza * 0.45)))
        n = puntas * 2
        radios = [random.uniform(0.86, 1.0) if i % 2 == 0 else random.uniform(0.56, 0.68) for i in range(n)]
        giro = random.uniform(0, math.tau)
        tamano = int(_RADIO_ESTALLIDO * 2 + 16)
        c = tamano / 2

        def estrella(escala):
            return [
                (
                    c + math.cos(giro + math.tau * i / n) * _RADIO_ESTALLIDO * radios[i] * escala,
                    c + math.sin(giro + math.tau * i / n) * _RADIO_ESTALLIDO * radios[i] * escala,
                )
                for i in range(n)
            ]

        lienzo = _Lienzo(tamano, tamano, self.SUPERMUESTREO)
        lienzo.limpiar(paleta["tinta"])
        lienzo.poligono(paleta["tinta"], estrella(1.0))
        lienzo.poligono(paleta["rayo"], estrella(0.95))
        return lienzo.reducir((tamano, tamano))

    def _dibujar_estallido(self, superficie, centro, estado, ms):
        tri = self.tristeza
        fuerza = self._suave(estado["gesto"] * 1.25)
        if fuerza <= 0.02:
            return
        radio_objetivo = _ANCHO * 0.5 * self.ESCALA_ESTALLIDO * estado["escala"]
        pulso = 1.0 + 0.04 * math.sin(ms * 0.03)
        escala = radio_objetivo / _RADIO_ESTALLIDO * (0.45 + 0.55 * fuerza) * pulso * (1.0 - tri * 0.2)
        if escala <= 0.02:
            return
        estallido = pygame.transform.rotozoom(self._estallido, ms * 0.03, escala)
        estallido.set_alpha(int(255 * min(1.0, fuerza * 1.6) * (1.0 - tri * 0.4)))
        superficie.blit(estallido, (centro.x - estallido.get_width() / 2, centro.y - estallido.get_height() / 2))

    # ------------------------------------------------------------------
    # La cara (se pinta en unidades lógicas sobre el lienzo)
    # ------------------------------------------------------------------
    def _pintar_cara(self, ms, estado, anterior):
        lienzo = self._lienzo
        paleta = self.paleta
        tri = self.tristeza
        gesto = _limitar(estado["gesto"])
        c = self._centro_lienzo
        grosor = _ANCHO * 0.045

        lienzo.limpiar(paleta["tinta"])

        # Movimiento secundario: el pelo se retrasa respecto a la cabeza.
        # Si la cara crece rápido, las puntas se doblan hacia abajo; si se
        # encoge rápido, se estiran hacia arriba.
        alto_ahora = estado["escala"] * (1.0 + estado["estirar"])
        alto_antes = anterior["escala"] * (1.0 + anterior["estirar"])
        arrastre = _limitar((alto_ahora - alto_antes) * 3.0, -1.0, 1.0)

        self._dibujar_pelo(lienzo, c, ms, arrastre, paleta)
        self._dibujar_cabeza(lienzo, c, ms, paleta, grosor)
        self._dibujar_mejillas(lienzo, c, paleta, tri)
        self._dibujar_ojos(lienzo, c, ms, gesto, paleta, grosor, tri)
        self._dibujar_cejas(lienzo, c, gesto, paleta, grosor, tri)
        self._dibujar_nariz(lienzo, c, paleta, grosor)
        self._dibujar_boca(lienzo, c, gesto, paleta, grosor, tri)
        self._dibujar_lagrima(lienzo, c, ms, paleta, tri)
        self._dibujar_sudor(lienzo, c, ms, paleta, tri)

    def _contorno_cabeza(self, c, fase, expansion=0.0, escala=1.0, dx=0.0, dy=0.0):
        """Cabeza irregular: un óvalo con mandíbula algo más ancha y un
        borde que ondula muy poco, como trazado a mano."""
        f1, f2, f3 = fase
        n = 56
        puntos = []
        for i in range(n):
            a = math.tau * i / n
            onda = 1.0 + 0.016 * math.sin(3 * a + f1) + 0.011 * math.sin(5 * a + f2) + 0.007 * math.sin(8 * a + f3)
            mandibula = 1.0 + 0.07 * math.sin(a)
            rx = (_ANCHO / 2 * mandibula * escala + expansion) * onda
            ry = (_ALTO / 2 * escala + expansion) * onda
            puntos.append((c.x + dx + rx * math.cos(a), c.y + dy + ry * math.sin(a)))
        return puntos

    def _dibujar_cabeza(self, lienzo, c, ms, paleta, grosor):
        fase = self._boil[int(ms / 90) % len(self._boil)]
        # Contorno grueso, sombreado tipo "cel" (media luna abajo a la
        # derecha) y piel desplazada hacia la luz.
        lienzo.poligono(paleta["tinta"], self._contorno_cabeza(c, fase, expansion=grosor))
        lienzo.poligono(paleta["sombra"], self._contorno_cabeza(c, fase))
        lienzo.poligono(paleta["piel"], self._contorno_cabeza(c, fase, escala=0.93, dx=-7.0, dy=-7.0))
        lienzo.elipse(
            paleta["piel_luz"],
            (c.x - _ANCHO * 0.17, c.y - _ALTO * 0.27),
            _ANCHO * 0.42,
            _ALTO * 0.26,
        )

    def _dibujar_pelo(self, lienzo, c, ms, arrastre, paleta):
        # Mechones puntiagudos y curvados asomando arriba de la cabeza,
        # como el pelo alborotado de los personajes de Maddocks. Ondean
        # un poco y reaccionan al movimiento de la cabeza.
        base_y = c.y - _ALTO * 0.42
        posiciones = (-0.22, 0.0, 0.22)
        largos = (0.16, 0.24, 0.14)
        for i, (desplazo, largo) in enumerate(zip(posiciones, largos)):
            bx = c.x + _ANCHO * desplazo
            aleteo = math.sin(ms * 0.028 + i * 1.9) * _ANCHO * 0.022
            punta_x = bx + _ANCHO * desplazo * 0.45 + aleteo
            punta_y = base_y - _ALTO * largo * (1.0 - 0.25 * abs(arrastre)) + arrastre * _ALTO * 0.10
            curva = _ANCHO * 0.035 * (1 if i % 2 == 0 else -1)
            control = (bx + (punta_x - bx) * 0.2 + curva, base_y + (punta_y - base_y) * 0.55)
            puntos = self._bezier_cuadratica((bx, base_y), control, (punta_x, punta_y), pasos=9)
            lienzo.trazo(paleta["pelo"], puntos, _ANCHO * 0.10, 2.0)

    def _dibujar_mejillas(self, lienzo, c, paleta, tri):
        # Rubor opaco mezclado con la piel (con ``draw`` sobre SRCALPHA un
        # color con alfa dejaría un agujero transparente en la cara).
        intensidad = 0.6 * (1.0 - tri * 0.85)
        if intensidad <= 0.03:
            return
        color = self._mezclar_color(paleta["piel"], paleta["rubor"], intensidad)
        for lado in (-1, 1):
            lienzo.elipse(color, (c.x + lado * _ANCHO * 0.34, c.y + _ALTO * 0.14), _ANCHO * 0.20, _ALTO * 0.12)

    def _dibujar_cejas(self, lienzo, c, gesto, paleta, grosor, tri):
        # Cejas finas y muy arqueadas, bien separadas de los ojos: el
        # trazo suelto y "en acento circunflejo" típico de Peter
        # Maddocks. Con tristeza, el arco se invierte hacia la clásica
        # ceja de preocupación: la punta interior sube y la exterior baja.
        separacion = _ANCHO * 0.26
        y = c.y - _ALTO * 0.31 - gesto * _ALTO * 0.11
        largo = _ANCHO * 0.24
        arco = largo * (0.45 + gesto * 0.35) * (1.0 - tri * 0.55)
        inclinacion_triste = tri * largo * 0.30
        for lado in (-1, 1):
            # Ligera asimetría para que no se vea calcado.
            asimetria = 1.0 if lado < 0 else 1.06
            x = c.x + lado * separacion
            p0 = (x - lado * largo / 2, y + arco * 0.22 - inclinacion_triste)
            p1 = (x + lado * largo * 0.05, y - arco * asimetria)
            p2 = (x + lado * largo * 0.75, y + arco * 0.16 + inclinacion_triste)
            puntos = self._bezier_cuadratica(p0, p1, p2, pasos=8)
            lienzo.trazo(paleta["tinta"], puntos, grosor * 0.55, grosor * 0.42, panza=0.7)

    def _parpadeo(self, ms):
        """0 = ojo abierto, 1 = cerrado. Un solo parpadeo suave a destiempo."""
        cercania = 1.0 - abs(ms - self._t_parpadeo) / 70.0
        return self._suave(max(0.0, cercania) * 1.3)

    @staticmethod
    def _parte_alta_del_circulo(cx, cy, r, y0, m, pasos=18):
        """Parte del círculo que queda por encima de la recta
        ``y = y0 + m * (x - cx)``. Devuelve ``(polígono, (p1, p2))`` con los
        extremos de la recta, o ``(None, None)`` si no hay nada que tapar."""
        d = y0 - cy
        if d <= -r:
            return None, None
        if d >= r:
            return [(cx + r * math.cos(math.tau * i / 24), cy + r * math.sin(math.tau * i / 24)) for i in range(24)], None
        disc = r * r * (1 + m * m) - d * d
        raiz = math.sqrt(max(0.0, disc))
        u1 = (-m * d - raiz) / (1 + m * m)
        u2 = (-m * d + raiz) / (1 + m * m)
        p1 = (cx + u1, y0 + m * u1)
        p2 = (cx + u2, y0 + m * u2)
        a1 = math.atan2(p1[1] - cy, u1)
        if a1 > 0:
            a1 -= math.tau
        a2 = math.atan2(p2[1] - cy, u2)
        if a2 < a1:
            a2 += math.tau
        arco = [
            (cx + r * math.cos(a1 + (a2 - a1) * i / pasos), cy + r * math.sin(a1 + (a2 - a1) * i / pasos))
            for i in range(pasos + 1)
        ]
        return arco, (p1, p2)

    def _dibujar_ojos(self, lienzo, c, ms, gesto, paleta, grosor, tri):
        # Ojos enormes y ligeramente asimétricos, con pupila grande: la
        # mirada bien abierta y algo boba de los personajes de Maddocks.
        # Con el susto los ojos se abultan y las pupilas se encogen; luego
        # siguen al jugador. El parpadeo aplasta el ojo verticalmente y el
        # párpado caído de la tristeza es una cuerda inclinada.
        cierre = self._parpadeo(ms)
        abierto = 1.0 - 0.94 * cierre
        y = c.y - _ALTO * 0.16 + tri * _ALTO * 0.03
        separacion = _ANCHO * 0.25
        radio_base = _ANCHO * 0.165 * (1.0 + 0.14 * gesto)
        borde = max(3.0, grosor * 0.45)
        # Un sobresalto se ve igual sea cual sea el humor: el párpado solo
        # actúa cuando ya no hay susto.
        parpado = 0.42 * tri * (1.0 - gesto)

        for lado in (-1, 1):
            x = c.x + lado * separacion
            radio = radio_base * (0.92 if lado < 0 else 1.0)
            lienzo.elipse(paleta["tinta"], (x, y), (radio + borde) * 2, (radio + borde) * 2 * abierto)
            lienzo.elipse((255, 255, 255), (x, y), radio * 2, radio * 2 * abierto)
            if cierre >= 0.85:
                continue

            radio_pupila = radio * (0.34 + 0.24 * (1.0 - gesto))
            desplazo = pygame.Vector2(self._mirada.x, self._mirada.y + tri * 0.9)
            largo = desplazo.length()
            maximo = (radio - radio_pupila) * 0.85
            if largo > 1.0:
                desplazo = desplazo / largo
                largo = 1.0
            desplazo = desplazo * (largo * maximo)
            # Las pupilas vibran un pelín mientras dura el susto.
            desplazo.x += math.sin(ms * 0.13 + lado) * gesto * 0.8
            pupila = (x + desplazo.x + lado * radio * 0.04, y + desplazo.y * abierto)
            lienzo.elipse(paleta["tinta"], pupila, radio_pupila * 2, radio_pupila * 2 * abierto)
            if abierto > 0.6:
                # Brillos: se achican con la tristeza (ojo apagado).
                brillo = (pupila[0] - radio * 0.22, pupila[1] - radio * 0.24)
                lienzo.circulo(paleta["brillo"], brillo, max(2.0, radio * (0.24 - tri * 0.14)))
                brillo_chico = (pupila[0] + radio * 0.28, pupila[1] + radio * 0.20)
                lienzo.circulo(paleta["brillo"], brillo_chico, max(1.5, radio * (0.10 - tri * 0.06)))

            if parpado > 0.02:
                y0 = y - radio + 2 * radio * parpado
                pendiente = tri * 0.28 * lado
                poligono, extremos = self._parte_alta_del_circulo(x, y, radio, y0, pendiente)
                if poligono:
                    poligono = [(px, y + (py - y) * abierto) for px, py in poligono]
                    lienzo.poligono(paleta["piel"], poligono)
                    if extremos:
                        (ax, ay), (bx, by) = extremos
                        cuerda = [(ax, y + (ay - y) * abierto), (bx, y + (by - y) * abierto)]
                        lienzo.trazo(paleta["tinta"], cuerda, grosor * 0.7)

    def _dibujar_nariz(self, lienzo, c, paleta, grosor):
        # Nariz larga y redondeada, con un ligero gancho hacia un lado:
        # rasgo protagonista en los rostros de Peter Maddocks, no un
        # simple punto. Baja desde el entrecejo casi hasta la sonrisa.
        y_arriba = c.y - _ALTO * 0.10
        y_abajo = c.y + _ALTO * 0.05
        gancho = _ANCHO * 0.05
        p0 = (c.x - _ANCHO * 0.015, y_arriba)
        p1 = (c.x + gancho, c.y + _ALTO * 0.08)
        p2 = (c.x + gancho * 0.6, y_abajo)
        puntos = self._bezier_cuadratica(p0, p1, p2, pasos=10)

        grosor_nariz = max(6.0, _ANCHO * 0.055)
        lienzo.trazo(paleta["tinta"], puntos, grosor_nariz + grosor * 0.4 + 1.0, grosor_nariz * 1.15 + grosor * 0.4 + 1.0)
        lienzo.trazo(paleta["sombra"], puntos, grosor_nariz, grosor_nariz * 1.15)

        # Bulbo redondeado en la punta, con su propio brillo.
        radio_bulbo = max(5.0, _ANCHO * 0.045)
        lienzo.circulo(paleta["tinta"], p2, radio_bulbo + max(2.0, grosor * 0.35))
        lienzo.circulo(paleta["rubor"], p2, radio_bulbo)
        lienzo.circulo(
            paleta["brillo"],
            (p2[0] - radio_bulbo * 0.35, p2[1] - radio_bulbo * 0.4),
            max(1.5, radio_bulbo * 0.32),
        )

    @staticmethod
    def _bordes_boca(y, alto, apertura, u):
        """Altura del borde superior e inferior de la boca en la columna
        ``u`` (-1 = comisura izquierda, 1 = derecha).

        Con ``apertura`` = 0 es una sonrisa en "D" (labio superior casi
        recto con las comisuras arriba, mentón redondeado); con
        ``apertura`` = 1 es un óvalo, la "O" de sorpresa. En medio se
        mezclan punto a punto, así la boca cambia sin saltos.
        """
        u2 = 1.0 - u * u
        mitad = alto / 2 * math.sqrt(max(0.0, u2))
        sup_d = y - alto * 0.5 + alto * 0.30 * u2
        inf_d = y - alto * 0.5 + alto * max(0.0, u2) ** 0.7
        return (sup_d + (y - mitad - sup_d) * apertura, inf_d + (y + mitad - inf_d) * apertura)

    def _contorno_boca(self, x, y, ancho, alto, apertura, expansion=0.0, n=24):
        puntos_inf, puntos_sup = [], []
        for i in range(n + 1):
            u = math.cos(math.pi * i / n)  # 1 -> -1, más denso en las comisuras
            sup, inf = self._bordes_boca(y, alto, apertura, u)
            puntos_inf.append((x + u * ancho / 2, inf))
            puntos_sup.append((x + u * ancho / 2, sup))
        puntos = puntos_inf + puntos_sup[::-1]
        if expansion:
            kx = 1.0 + expansion / max(1.0, ancho / 2)
            ky = 1.0 + expansion / max(1.0, alto / 2)
            puntos = [(x + (px - x) * kx, y + (py - y) * ky) for px, py in puntos]
        return puntos

    def _dibujar_boca(self, lienzo, c, gesto, paleta, grosor, tri):
        """Boca única que se transforma sin cortes entre la "O" de sorpresa
        y la sonrisa amplia, según ``gesto`` (1 = sorpresa, 0 = sonrisa).

        Es una sola forma que interpola tamaño, color de la cavidad y la
        aparición gradual de dientes/lengua, así el gesto fluye en vez de
        "saltar". ``tri`` reparte la posición de reposo (``gesto`` = 0)
        entre una sonrisa con dientes y un puchero con las comisuras hacia
        abajo; la "O" de sorpresa se mantiene igual en ambos casos.
        """
        tinta, lengua, brillo = paleta["tinta"], paleta["lengua"], paleta["brillo"]
        apertura = _limitar(gesto)
        factor_sonrisa = 1.0 - apertura
        factor_alegre = factor_sonrisa * (1.0 - tri)
        factor_triste = factor_sonrisa * tri
        x = c.x
        y = c.y + _ALTO * (0.27 + apertura * 0.05)

        radio_o = _ANCHO * 0.11
        ancho_boca = _ANCHO * (0.70 * factor_alegre + 0.40 * factor_triste) + radio_o * 2 * apertura
        alto_boca = _ALTO * (0.36 * factor_alegre + 0.16 * factor_triste) + radio_o * 2 * apertura
        # En el puchero la cavidad desaparece: solo queda la línea.
        presencia = min(1.0, (apertura + factor_alegre) * 1.25)

        if presencia > 0.04:
            ancho_e, alto_e = ancho_boca * presencia, alto_boca * presencia
            borde = grosor * 0.9
            lienzo.poligono(tinta, self._contorno_boca(x, y, ancho_e, alto_e, apertura, expansion=borde))
            # Comisuras redondeadas en vez de picos (solo en la sonrisa: el
            # óvalo de la "O" no tiene picos que redondear).
            if factor_alegre > 0.05:
                for lado in (-1, 1):
                    sup, _ = self._bordes_boca(y, alto_e, apertura, lado)
                    radio = borde * 0.95 * min(1.0, factor_alegre * 2.0)
                    lienzo.circulo(tinta, (x + lado * (ancho_e / 2 + borde * 0.35), sup - borde * 0.35), radio)
            # La cavidad pasa de un tono lengua (boca "O") a un fondo
            # oscuro (boca sonriente, donde se ven los dientes de encima).
            cavidad = self._mezclar_color(tinta, lengua, apertura)
            lienzo.poligono(cavidad, self._contorno_boca(x, y, ancho_e, alto_e, apertura))

            if factor_alegre > 0.03:
                # Todo opaco: la aparición gradual se hace mezclando con
                # el color de la cavidad.
                a = min(1.0, factor_alegre * 1.3)
                _, fondo = self._bordes_boca(y, alto_e, apertura, 0.0)
                lienzo.elipse(
                    self._mezclar_color(cavidad, lengua, a),
                    (x, fondo - alto_e * 0.17),
                    ancho_e * 0.52,
                    alto_e * 0.27,
                )
                color_diente = self._mezclar_color(cavidad, brillo, a)
                color_linea = self._mezclar_color(color_diente, tinta, a)
                # Dientes: siguen la curva del labio superior.
                divisiones = 6
                grosor_linea = max(1.4, grosor * 0.25)
                arriba, abajo = [], []
                for i in range(17):
                    u = -0.94 + 1.88 * i / 16
                    sup, inf = self._bordes_boca(y, alto_e, apertura, u)
                    y_alto = sup + 1.5
                    y_bajo = max(y_alto + 1.0, min(sup + alto_e * 0.30, inf - 1.0))
                    arriba.append((x + u * ancho_e / 2, y_alto))
                    abajo.append((x + u * ancho_e / 2, y_bajo))
                lienzo.poligono(color_diente, arriba + abajo[::-1])
                lienzo.trazo(color_linea, abajo, grosor_linea)
                for i in range(1, divisiones):
                    u = -0.94 + 1.88 * i / divisiones
                    sup, inf = self._bordes_boca(y, alto_e, apertura, u)
                    y_alto = sup + 1.5
                    y_bajo = max(y_alto + 1.0, min(sup + alto_e * 0.30, inf - 1.0))
                    lienzo.trazo(color_linea, [(x + u * ancho_e / 2, y_alto), (x + u * ancho_e / 2, y_bajo)], grosor_linea * 0.8)

            if factor_alegre > 0.25:
                # Hoyuelos: pequeños paréntesis junto a las comisuras.
                grosor_h = grosor * 0.6 * min(1.0, (factor_alegre - 0.25) * 2.0)
                for lado in (-1, 1):
                    sup, _ = self._bordes_boca(y, alto_e, apertura, lado)
                    xe = x + lado * (ancho_e / 2 + borde + 5.0)
                    puntos = self._bezier_cuadratica(
                        (xe - lado * 3.0, sup - alto_e * 0.06),
                        (xe + lado * 8.0, sup + alto_e * 0.16),
                        (xe - lado * 3.0, sup + alto_e * 0.38),
                        pasos=6,
                    )
                    lienzo.trazo(tinta, puntos, grosor_h, grosor_h * 0.5)

        if factor_triste > 0.03:
            # Comisuras hacia abajo: el clásico puchero, con la misma
            # técnica de curva Bézier que las cejas.
            ancho_puchero = ancho_boca * 0.85
            caida = alto_boca * 0.55
            p0 = (x - ancho_puchero / 2, y + caida)
            p1 = (x, y - alto_boca * 0.10)
            p2 = (x + ancho_puchero / 2, y + caida)
            puntos = self._bezier_cuadratica(p0, p1, p2, pasos=10)
            grosor_puchero = max(2.0, grosor * 0.75 * min(1.0, factor_triste * 1.4))
            lienzo.trazo(tinta, puntos, grosor_puchero, grosor_puchero * 0.6, panza=0.5)

    @staticmethod
    def _gota(lienzo, pos, radio, paleta):
        """Gota con forma de lágrima (punta arriba) y contorno de tinta."""
        x, y = pos
        for r, color in ((radio + 2.5, paleta["tinta"]), (radio, paleta["brillo"])):
            lienzo.poligono(color, [(x, y - r * 2.2), (x - r * 0.9, y - r * 0.3), (x + r * 0.9, y - r * 0.3)])
            lienzo.circulo(color, (x, y), r)

    def _dibujar_lagrima(self, lienzo, c, ms, paleta, tri):
        """Una lagrimita que solo aparece en los niveles más tristes
        (tristeza > 0.6) y va resbalando por la mejilla."""
        aparicion = _limitar((tri - 0.6) / 0.4)
        if aparicion <= 0.0:
            return
        avance = _limitar((ms - self.DURACION_SALIDA) / self.DURACION_ENTRADA)
        x = c.x + _ANCHO * 0.25
        y = c.y + _ALTO * 0.04 + avance * _ALTO * 0.20 * aparicion
        self._gota(lienzo, (x, y), (4.5 + 3.0 * aparicion) * min(1.0, ms / 300.0), paleta)

    def _dibujar_sudor(self, lienzo, c, ms, paleta, tri):
        """Gotas de sudor que salen disparadas de las sienes con el susto
        (el recurso clásico de los dibujos animados). Con tristeza casi no
        hay: un personaje decaído no se sobresalta con tanta energía."""
        for lado, vx, vy, retraso, tamano in self._gotas:
            t = ms / 1000.0 - 0.23 - retraso
            if t <= 0.0:
                continue
            vida = t / 0.75
            if vida >= 1.0:
                continue
            radio = 8.0 * tamano * min(1.0, t * 9.0) * (1.0 - self._suave((vida - 0.6) / 0.4)) * (1.0 - tri * 0.9)
            if radio < 0.8:
                continue
            x = c.x + lado * (_ANCHO * 0.40 + vx * t)
            y = c.y - _ALTO * 0.24 + vy * t + 0.5 * 550.0 * t * t
            self._gota(lienzo, (x, y), radio, paleta)