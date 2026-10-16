# 🎮 Proyecto Mr. Pati

> Juego de plataformas desarrollado en Python con Pygame y OpenCV.

---

## 📋 Requisitos Previos

- **Python:** `3.12`
- **Librerías principales:** `pygame`, `opencv-python`

---

## 🚀 Instalación y Ejecución

1. Clona el repositorio e ingresa a la carpeta del proyecto.
2. Crea y activa tu entorno virtual (opcional pero recomendado):
   ```bash
   python -m venv .venv
   # En Windows:
   .venv\Scripts\activate
   ```
3. Instala las dependencias necesarias:
   ```bash
   pip install pygame opencv-python
   ```
4. Inicia el juego desde la entrada principal:
   ```bash
   python juego.py
   ```
   El juego guarda automáticamente el último nivel alcanzado y, al volver a
   iniciar, el botón **Continuar** retoma la partida desde el comienzo de ese
   nivel. Si la partida termina, el progreso se reinicia.

---

## 🛠️ Comandos de Administración y Opciones

Puedes ejecutar el juego pasando argumentos desde la línea de comandos para facilitar pruebas o cambiar configuraciones.

### Cargar Nivel Específico
```bash
python juego.py --nivel 5
```
*Si usas PowerShell dentro de un entorno virtual:*
```powershell
& .venv\Scripts\python.exe juego.py --nivel 5
```

### Cambio de Idioma
```bash
python juego.py --idioma [código]
```

**Idiomas disponibles:**
- `es`: Español 🇪🇸
- `en`: Inglés 🇬🇧
- `pt`: Portugués 🇵🇹
- `ru`: Ruso 🇷🇺

---

---

## 🎬 Sistema de Créditos y Final del Juego

Al completar el **Nivel 40**, se activa automáticamente la escena final, seguida de los créditos cinematográficos de *Mr Pati*. 

Esta secuencia incluye un carrusel animado con todo el material gráfico empleado en el juego. Toda la lógica de esta pantalla está implementada dentro del módulo `creditos.py`.

### 🔍 Visualización de Animaciones Independientes
Si deseas probar, revisar o auditar el detalle de las animaciones de manera aislada sin necesidad de completar todo el juego, puedes ejecutar los módulos correspondientes de forma independiente:

- **Animación Catarsis:**
  ```bash
  python catarsis.py
- **Animación Final:**
  ```bash
  python alfin.py
- **Animacion despertar:**
  ```bash
  python despertar.py

## 📊 Pruebas de Rendimiento

El motor del juego mantiene una tasa de cuadros estable objetivo de **~60 FPS** a lo largo de las distintas etapas de desarrollo:

- **Niveles Básicos (1 - 20):** 
  - **FPS Promedio:** 51.0 - 60.6 FPS.
  - **Física:** ~0.13 ms - 0.28 ms promedio.
  - **Render:** ~9.14 ms - 12.29 ms promedio.
  
- **Niveles Altos (20 - 40):** 
  - **FPS Promedio:** 51.8 - 62.1 FPS.
  - **Física:** ~0.00 ms - 0.19 ms promedio.
  - **Render:** ~1.40 ms - 11.48 ms promedio.