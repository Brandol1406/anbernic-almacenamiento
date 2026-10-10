# Almacenamiento para Anbernic (sistema original)

App para la sección **APPS** del sistema original de Anbernic (consolas H700 como la RG34XX SP)
que muestra el espacio libre de las dos tarjetas microSD y qué carpetas de `Roms` ocupan más.

| Pantalla principal | Qué ocupa espacio en Roms |
|---|---|
| ![Pantalla principal](docs/pantalla-principal.png) | ![Roms](docs/pantalla-roms.png) |

## Qué muestra

- **SD 2 – Juegos** (`/mnt/sdcard`) y las 4 particiones de la **SD 1** (sistema, apps, datos y la partición visible).
- Una barra por unidad: verde hasta 75 %, amarilla hasta 90 %, roja por encima.
- Con **A**, el tamaño de cada carpeta de `Roms` en la SD 2, de mayor a menor (tarda unos segundos: usa `du`).

## Botones

| Botón | Acción |
|---|---|
| A | Ver qué ocupa espacio en Roms |
| ◀ ▶ | Cambiar de página (en la lista de Roms) |
| B | Volver / salir |
| MENU | Salir |

## Instalación

Copia el contenido del repositorio en la carpeta `Roms/APPS` de cualquiera de las dos tarjetas
(el menú lee las dos):

```
Roms/APPS/Almacenamiento.sh
Roms/APPS/storage/main.py
Roms/APPS/Imgs/Almacenamiento.png
```

No necesita instalar nada: usa `python3` y `Pillow`, que ya vienen en el sistema de Anbernic.

## Cómo funciona

El sistema de Anbernic no tiene un toolkit gráfico para apps; las apps oficiales (como el Reloj)
dibujan directamente en el **framebuffer**. Esta app hace lo mismo:

1. **Dibuja con Pillow** una imagen de 720×480 en memoria.
2. **La escribe en `/dev/fb0`** mediante `mmap`, convirtiéndola a formato `BGRA` (el orden de color de la pantalla).
3. Antes aplica la configuración de pantalla que usan las apps oficiales (`/mnt/mod/ctrl/configs/fb.cfg`)
   con `ioctl(FBIOPUT_VSCREENINFO)`.
4. **El framebuffer tiene doble búfer** (720×960 = dos "páginas"), y el menú suele dejar visible la
   segunda (`/sys/class/graphics/fb0/pan` = `0,480`). Por eso la imagen se escribe en **todas** las
   páginas; si solo se escribe en la primera, la pantalla queda negra.
5. **Los botones** se leen de `/dev/input/event1` como eventos `evdev` de 24 bytes
   (A = 304, B = 305, MENU = 312, la cruceta llega como ejes `ABS_HAT0X/Y`).
6. El espacio se obtiene con `shutil.disk_usage()`; el detalle de Roms con `du -sk`.

Para probar sin tocar la pantalla (por ejemplo por SSH): `python3 storage/main.py --png salida.png`.

## Compatibilidad

Probado en una **RG34XX SP** con el sistema original **1.0.6**. Debería funcionar en otras consolas
H700 de Anbernic con pantalla de 720×480; en otras resoluciones habría que ajustar `W` y `H`.
