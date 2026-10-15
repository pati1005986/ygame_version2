# Contributing Guide

Thank you for your interest in contributing to **Mr. Pati**! This is a platform game developed in Python with Pygame. OpenCV is used in the credits system.

## Before you start

- Read the [README](./README.md) to learn about the game and how to run it.
- Review the [Code of Conduct](./CODE_OF_CONDUCT.md) and keep all communication respectful.
- For larger changes, open an issue first and describe the problem it solves or the proposal you would like to develop. For small, clearly defined fixes, you can open a pull request directly.
- Make sure you have permission to share any images, audio, fonts, or other assets you add.

## Set up your environment

Python 3.12 is recommended. From the repository directory, create and activate a virtual environment, then install the dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install pygame opencv-python pytest
```

If PowerShell does not allow you to activate the environment, you can run its tools directly:

```powershell
.\.venv\Scripts\python.exe -m pip install pygame opencv-python pytest
```

Start the game with:

```powershell
python juego.py
```

## Contribution process

1. Create a branch for your change, for example `fix/platform-movement` or `feature/french-language`.
2. Keep changes focused and follow the existing style: use descriptive Spanish names, small modules, and responsibilities that fit the game's structure.
3. If you change visible text, review the translations and behavior in `idioma.py`.
4. If you modify movement, collisions, events, options, or transitions, check how the change affects levels and other entities.
5. Run the tests before submitting your change:

   ```powershell
   python -m pytest
   ```

6. Manually test the game with `python juego.py` when your change affects gameplay, the interface, audio, or assets.
7. Open a pull request with a summary of the change, the related issue (if any), the tests you ran, and screenshots or a description of the result for visual changes.

## What to include in a pull request

- Explain what changed and why.
- List the test commands you ran and whether they passed.
- Add or update tests for behavior changes where appropriate.
- Update related documentation if installation, controls, or game behavior changes.
- Do not include temporary files, personal configuration, or unnecessary dependencies.

---

# Guía de contribución

¡Gracias por tu interés en contribuir a **Mr. Pati**! Este es un juego de plataformas desarrollado en Python con Pygame. OpenCV se utiliza en el sistema de créditos.

## Antes de empezar

- Revisa el [README](./README.md) para conocer el juego y cómo ejecutarlo.
- Consulta el [Código de conducta](./CODE_OF_CONDUCT.md) y mantén una comunicación respetuosa.
- Para cambios grandes, abre primero un issue y comenta qué problema resuelve o qué propuesta quieres desarrollar. Para errores pequeños y claros, puedes abrir directamente un pull request.
- Comprueba que tienes permiso para compartir cualquier imagen, sonido, fuente u otro recurso que quieras añadir.

## Preparar el entorno

Se recomienda Python 3.12. Desde la carpeta del repositorio, crea y activa un entorno virtual e instala las dependencias:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install pygame opencv-python pytest
```

Si PowerShell no permite activar el entorno, puedes ejecutar sus herramientas directamente:

```powershell
.\.venv\Scripts\python.exe -m pip install pygame opencv-python pytest
```

Inicia el juego con:

```powershell
python juego.py
```

## Proceso de contribución

1. Crea una rama para tu cambio, por ejemplo `fix/movimiento-plataformas` o `feature/idioma-frances`.
2. Mantén los cambios enfocados y sigue el estilo existente: nombres descriptivos en español, módulos pequeños y responsabilidades coherentes con la estructura del juego.
3. Si cambias textos visibles, revisa las traducciones y el comportamiento en `idioma.py`.
4. Si modificas movimiento, colisiones, eventos, opciones o transiciones, comprueba también cómo afecta a los niveles y a las demás entidades.
5. Ejecuta las pruebas antes de enviar el cambio:

   ```powershell
   python -m pytest
   ```

6. Prueba manualmente el juego con `python juego.py` cuando el cambio afecte la experiencia de juego, la interfaz, el audio o los recursos.
7. Abre un pull request con un resumen del cambio, el problema relacionado (si existe), las pruebas realizadas y, para cambios visuales, capturas o una descripción del resultado.

## Qué incluir en un pull request

- Explica qué cambia y por qué.
- Indica los comandos de prueba ejecutados y si pasaron.
- Incluye o actualiza pruebas para cambios de comportamiento cuando corresponda.
- Actualiza la documentación relacionada si cambian la instalación, los controles o el funcionamiento del juego.
- Evita incluir archivos temporales, configuraciones personales o dependencias que no sean necesarias.
