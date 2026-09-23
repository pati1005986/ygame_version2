import pygame

from transicion import TransicionCaricaturesca
from idioma import alternar_idioma, texto
from opciones import MenuOpciones, cargar_configuracion, guardar_configuracion


def test_transicion_se_pone_triste_a_partir_del_nivel_10():
    nivel_9 = TransicionCaricaturesca(
        (255, 255, 255),
        (0, 0, 0),
        (100, 100),
        (200, 200),
        nivel=9,
    )
    nivel_10 = TransicionCaricaturesca(
        (255, 255, 255),
        (0, 0, 0),
        (100, 100),
        (200, 200),
        nivel=10,
    )
    nivel_18 = TransicionCaricaturesca(
        (255, 255, 255),
        (0, 0, 0),
        (100, 100),
        (200, 200),
        nivel=18,
    )
    assert nivel_9.nivel == 9
    assert nivel_9.tristeza == 0.0
    assert nivel_10.nivel == 10
    assert nivel_10.tristeza == 0.0
    assert nivel_18.nivel == 18
    assert nivel_18.tristeza == 1.0


def test_alternar_idioma_incluye_portugues_y_ruso():
    assert alternar_idioma("en") == "es"
    assert alternar_idioma("es") == "pt"
    assert alternar_idioma("pt") == "ru"
    assert alternar_idioma("ru") == "en"


def test_textos_de_nuevos_idiomas():
    assert texto("pt", "play") == "JOGAR"
    assert texto("ru", "options") == "ОПЦИИ"
    assert texto("pt", "language") == "IDIOMA"
    assert texto("ru", "language") == "ЯЗЫК"


def test_textos_de_opciones_nuevas():
    assert texto("en", "music") == "MUSIC"
    assert texto("es", "effects") == "EFECTOS"
    assert texto("es", "reset_defaults") == "RESTAURAR PREDETERMINADO"


def test_guardar_y_cargar_configuracion_persistente(tmp_path):
    ruta = tmp_path / "config_guardada.json"
    configuracion = {
        "resoluciones": MenuOpciones.RESOLUCIONES,
        "resolucion": 1,
        "pantalla_completa": True,
        "idioma": "pt",
        "volumen_musica": 0.35,
        "volumen_efectos": 0.65,
        "controles": {
            "left": pygame.K_q,
            "right": pygame.K_e,
            "jump": pygame.K_w,
            "down": pygame.K_x,
        },
    }

    guardar_configuracion(configuracion, ruta)
    cargada = cargar_configuracion(ruta)

    assert cargada["idioma"] == "pt"
    assert cargada["volumen_musica"] == 0.35
    assert cargada["volumen_efectos"] == 0.65
    assert cargada["controles"]["jump"] == pygame.K_w
    assert cargada["resolucion"] == 1
    assert cargada["pantalla_completa"] is True
