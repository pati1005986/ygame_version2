from idioma import alternar_idioma, texto


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
