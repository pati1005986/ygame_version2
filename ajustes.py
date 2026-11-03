"""Carga/normalización de la configuración y control del volumen."""

import pygame

from opciones import MenuOpciones, cargar_configuracion, normalizar_configuracion

IDIOMAS_DISPONIBLES = {"en", "es", "pt", "ru"}


def _limitar(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))


def preparar_configuracion(idioma_inicial):
    """Lee la configuración guardada y la deja validada y completa."""
    guardada = cargar_configuracion()
    configuracion = normalizar_configuracion(guardada)
    resoluciones = MenuOpciones.resoluciones_configuracion()
    configuracion["resoluciones"] = resoluciones
    indice_resolucion = configuracion["resolucion"]
    if indice_resolucion >= len(resoluciones):
        try:
            escritorio = pygame.display.get_desktop_sizes()[0]
        except (pygame.error, AttributeError, IndexError):
            escritorio = None
        configuracion["resolucion"] = (
            resoluciones.index(escritorio)
            if escritorio in resoluciones
            else 0
        )

    idioma = configuracion.get("idioma", idioma_inicial)
    configuracion["idioma"] = idioma if idioma in IDIOMAS_DISPONIBLES else idioma_inicial
    configuracion["pantalla_completa"] = bool(
        configuracion.get("pantalla_completa", False)
    )
    configuracion["volumen_musica"] = _limitar(
        float(configuracion.get("volumen_musica", 0.8)), 0.0, 1.0
    )
    configuracion["volumen_efectos"] = _limitar(
        float(configuracion.get("volumen_efectos", 0.8)), 0.0, 1.0
    )
    configuracion["escala_ui"] = float(configuracion.get("escala_ui", 1.0))
    if configuracion["escala_ui"] not in MenuOpciones.ESCALAS_UI:
        configuracion["escala_ui"] = 1.0

    configuracion["controles"] = MenuOpciones.DEFAULTS["controles"].copy()
    configuracion["controles"].update(guardada.get("controles", {}))
    return configuracion


def aplicar_volumen_audio(configuracion, jugador=None):
    """Aplica el volumen general a todas las fuentes de audio del juego."""
    volumen = _limitar(
        float(
            configuracion.get(
                "volumen_musica", configuracion.get("volumen_efectos", 0.8)
            )
        ),
        0.0,
        1.0,
    )
    configuracion["volumen_musica"] = volumen
    configuracion["volumen_efectos"] = volumen
    if pygame.mixer.get_init():
        pygame.mixer.music.set_volume(volumen)
    if jugador is not None:
        jugador.ajustar_volumen_efectos(volumen)