"""Curva de dificultad centralizada.

Antes, cada sistema decidía por su cuenta cómo escalar con el nivel:
``ajustar_dificultad_jugador`` (en ``juego.py``) subía la velocidad y la
gravedad del jugador, pero la probabilidad de que una plataforma se
moviera (``Plataforma.PROBABILIDAD_MOVIMIENTO``) y la velocidad de los
enemigos (``EntidadGris.velocidad_patrulla`` / ``velocidad_persecucion``)
se quedaban fijas para siempre. El resultado con el tiempo: el jugador se
vuelve más rápido nivel a nivel, pero los enemigos no lo acompañan, así
que dejan de sentirse amenazantes exactamente cuando el juego "cree" que
se está poniendo más difícil.

``parametros_dificultad(nivel)`` contiene la curva de historia y
``parametros_dificultad_infinito(nivel)`` la curva creciente del modo
infinito. Los generadores de niveles y los ajustes del jugador usan estas
funciones para mantener ambas progresiones centralizadas.

Cada valor tiene un techo (``min(..., tope)``) para que la dificultad se
estabilice en partidas muy largas en vez de crecer sin límite.
"""

import math


def parametros_dificultad(nivel):
    """Devuelve los parámetros de dificultad para ``nivel``.

    Hasta el nivel 30 la curva sube linealmente hasta sus tope. A partir de
    ahí, el juego vuelve a la línea base del nivel 1 y luego se hace más
    fácil progresivamente para relajar la experiencia en niveles muy altos.
    """
    # Usamos una función de progresión que crece inicialmente más rápido (ej: raíz)
    # pero aún respeta un tope aparente hasta N=30.
    if nivel <= 30:
        # Se usa max(1, ...) para asegurar al menos un progreso inicial positivo en el nivel 2.
        progreso = min(nivel - 1, int(1 + (nivel - 1) * 0.45)) # Curva ligeramente más pronunciada
        factor = 1.0
    else:
        # Desde el nivel 30 se reinicia a la dificultad del nivel 1; a partir
        # de ahí baja suavemente para que quede todo mucho más cómodo.
        progreso = 0
        # Se suaviza la caída inicial: en lugar de -0.08, usamos un valor menor y más constante.
        factor = max(0.5, 1.0 - (nivel - 30) * 0.06)


    # Ajuste de coeficientes: Aumentar el inicio del jugador para dar más peso al reto inicial.
    jugador_base = 8.0 + progreso * 0.12 # Inicio en 8.0, no 6.0
    gravedad_base = 0.7 + progreso * 0.018 # Inicio ligeramente más alto
    prob_movil_base = 0.25 + progreso * 0.015 # Mayor probabilidad inicial para sensación de reto
    patrulla_base = 2.0 + progreso * 0.04 # Ligeramente menor aumento, ya que el inicio es mayor.
    persecucion_base = 3.5 + progreso * 0.06 # Menor crecimiento en persecución para evitar picos muy grandes
    rango_base = 240 + progreso * 4
    return {
        # Jugador: a partir del 30 vuelve a la línea base y luego se relaja.
        "velocidad_jugador": min(jugador_base * factor, 9.0), # Aumento el cap ligeramente para permitir más variedad
        "gravedad_jugador": min(gravedad_base * factor, 1.0),
        # Plataformas y enemigos vuelven a ser mucho más suaves desde el 30.
        "probabilidad_plataforma_movil": min(prob_movil_base * factor, 0.65), # Aumento cap para que la fase de reto sea más alta
        "velocidad_enemigo_patrulla": min(patrulla_base * factor, 3.4),
        "velocidad_enemigo_persecucion": min(persecucion_base * factor, 5.2),
        "rango_deteccion_enemigo": min(rango_base * factor, 340), # Aumento cap de rango
    }


def _tiende(progreso, base, limite, k):
    """Va de ``base`` hacia ``limite`` sin alcanzarlo nunca.

    ``k`` es la "lentitud": con progreso == k ya se recorrió ~63 % del
    camino. Sirve tanto para subir como para bajar (``limite < base``).
    """
    return limite - (limite - base) * math.exp(-progreso / k)


def _crece(progreso, base, escala, k):
    """Crecimiento logarítmico: rápido al inicio y cada vez más lento, pero
    sin techo duro (el infinito de verdad)."""
    return base + escala * math.log1p(progreso / k)


def parametros_dificultad_infinito(nivel):
    """Curva frenética del modo infinito: la dificultad está en controlar.

    * Sube la energía: velocidad máxima y aceleración.
    * Baja el agarre: se frena y se corrige peor (derrapa más, gira peor,
      en el aire casi no pierde inercia).
    * El salto no cambia: la gravedad queda fija, así que ``altura_maxima_salto``
      y el generador de niveles siguen siendo coherentes.
    * ``deriva`` es un tambaleo lateral suave (aceleración en px/frame²).

    Las claves de agarre son opcionales para ``aplicar_agarre``: la curva de
    historia no las define y el personaje usa sus constantes de clase.
    """
    p = max(0, nivel - 1)
    return {
        # --- Energía ---
        "velocidad_jugador": _tiende(p, 8.0, 15.0, 35),
        "aceleracion_suelo": _tiende(p, 1.15, 1.9, 40),

        # --- Agarre (valores iniciales = constantes de PersonajeHumanoide) ---
        "friccion_suelo": _tiende(p, 0.95, 0.22, 30),    # frenada sin input
        "factor_giro": _tiende(p, 1.8, 1.0, 40),         # frenada al invertir
        "aceleracion_aire": _tiende(p, 0.65, 0.85, 40),
        "friccion_aire": _tiende(p, 0.25, 0.08, 40),     # casi no frena en el aire

        # --- Inestabilidad ---
        "deriva": min(_crece(p, 0.0, 0.16, 25), 0.5),

        # --- Salto: quieto ---
        "gravedad_jugador": 0.7,

        # --- Mundo ---
        "probabilidad_plataforma_movil": _tiende(p, 0.25, 0.85, 40),
        "velocidad_enemigo_patrulla": _crece(p, 2.0, 1.4, 20),
        "velocidad_enemigo_persecucion": _crece(p, 3.5, 2.4, 20),
        "rango_deteccion_enemigo": _tiende(p, 240, 480, 40),
    }