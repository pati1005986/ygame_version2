from transicion import TransicionCaricaturesca
from idioma import alternar_idioma, texto


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
