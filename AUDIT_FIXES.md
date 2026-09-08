# Correcciones de auditoría — septiembre de 2026

Esta revisión corrige los ocho hallazgos de la auditoría del código local y refuerza su validación. Conserva los cambios previos del proyecto. No implica una certificación empresarial ni una medición nueva de precisión sobre una biblioteca musical real.

## Cambios

1. **Selección segura.** La similitud acústica ya no se trata como una relación transitiva. Cada candidato automático debe tener evidencia suficiente con la copia recomendada, o con su componente de identidad exacta. Si falta esa evidencia, el grupo exige revisión y queda sin selecciones de borrado. La evidencia se guarda en la sesión y se comprueba en el servicio de archivos, incluso si se cambia la copia conservada. Las sesiones acústicas antiguas sin evidencia necesitan una revisión nueva.
2. **FFmpeg incluido.** La comparación PCM usa el ejecutable resuelto por la aplicación. La compilación exige FFmpeg, FFprobe y Chromaprint y los incorpora como binarios; su verificación inspecciona el archivo de PyInstaller y rechaza paquetes incompletos o que contengan bases de datos.
3. **Procesos controlados.** La comparación completa calcula hashes SHA-256 y longitudes del PCM sin almacenar el audio completo. Tiene límites de tiempo total y de inactividad, rechaza salidas fallidas y admite cancelación. Al terminar, cierra los procesos. Las operaciones de archivos de la GUI trabajan en un hilo separado con un diálogo modal de progreso; la reproducción se detiene en el hilo de la interfaz.
4. **Errores visibles.** El scanner conserva la cobertura del agrupador, contabiliza los errores de archivos una vez y comunica resultados incompletos en GUI y CLI. Los errores inesperados del worker se muestran en la interfaz. Los directorios inaccesibles también invalidan la cobertura completa.
5. **Candidatos acotados.** La tabla de pares tiene un límite estricto de admisión, incluso cuando todos los pares tienen muchas coincidencias. El orden es determinista y se informa el trabajo descartado. Las tareas de comparación se envían en una ventana acotada.
6. **Identidad exacta eficiente.** Los grupos SHA usan un representante y evidencia lineal. La verificación PCM omite las copias ya confirmadas por SHA. El agrupamiento final recorre aristas existentes, no todas las parejas de cada grupo. El presupuesto de verificación PCM también está acotado y su agotamiento marca cobertura parcial.
7. **Caché consistente.** Una firma versionada de extracción incluye duración mínima y análisis espectral. Los cambios de esas opciones fuerzan nuevo análisis; las opciones que solo afectan la comparación no lo hacen. Una migración aditiva conserva la base anterior y persiste también la evaluación espectral.
8. **Sesiones recuperables.** Un JSON válido con estructura inválida intenta recuperar el respaldo. Guardar después de una corrupción no sustituye un respaldo válido con la sesión corrupta.

## Validación reproducible

Entorno usado: Windows, Python 3.12, dependencias del archivo requirements-lock.txt y pytest fijado en requirements-dev.txt. Se usan archivos temporales y APPDATA aislado.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts/validate_project.py
.\.venv\Scripts\python.exe scripts/smoke_release.py
```

FFmpeg, FFprobe y fpcalc deben estar en `bin/` o PATH para la validación. El script verifica este requisito antes de ejecutar las pruebas. La primera ejecución tras actualizar puede reanalizar archivos de la caché anterior.

Pruebas añadidas: aristas negativas o ausentes entre candidatos y copia conservada; rechazo real de operaciones sin evidencia; 10,000 copias exactas con 9,999 reportes y ninguna decodificación PCM redundante; límite de candidatos; cancelación; procesos que se bloquean o producen salida sin terminar; igualdad PCM con límites de lectura diferentes; errores de proceso; actualización de caché; cobertura parcial; recuperación y respaldo de sesiones; evidencia persistente; y continuidad del bucle de eventos Qt durante operaciones.

El smoke test genera tres WAV, incluyendo una copia binaria y otra con metadatos distintos. Hace dos escaneos para probar la caché, verifica clasificación EXACT_AUDIO y comprueba byte por byte que dry-run no modifica archivos. Con `--exe`, elimina FFmpeg y FFprobe externos del PATH del proceso para comprobar la autonomía del paquete.

## Endurecimiento posterior con pruebas adversarias

Una segunda evaluación encontró que Chromaprint puede dar una coincidencia muy alta a archivos que comparten el fragmento analizado, aunque el resto sea distinto. Por esa razón, las coincidencias `ACOUSTIC_DUPLICATE` ahora siempre requieren revisión manual y nunca reciben acciones automáticas. `EXACT_HASH` y `EXACT_AUDIO`, que tienen verificación completa, conservan la selección automática.

El modo backup ahora aplica la misma revalidación previa que papelera y eliminación: si el origen o la copia conservada cambió después del escaneo, la operación se bloquea. La copia se escribe primero con un nombre privado, se sincroniza, se verifica por SHA-256 y se publica antes de retirar el origen. El journal guarda el hash esperado y la ruta temporal. En el arranque, una copia parcial se retira si el origen sigue presente; si el origen ya no está, solo un destino con el hash esperado permite completar la sincronización. Los registros antiguos sin hash quedan en estado de fallo para inspección manual.

La evaluación adversaria obtuvo cero selecciones automáticas en ocho casos distintos, incluidos finales sustituidos, silencio añadido, edición intermedia e introducción diferente. Las tres equivalencias exactas sí quedaron seleccionadas. Las dos transcodificaciones MP3 se detectaron acústicamente y quedaron protegidas para revisión.

Se inyectaron cierres reales de procesos en cuatro puntos de backup y cuatro puntos de eliminación permanente, además de unidad desconectada simulada, archivo cambiado en los tres modos, copia interrumpida y backup corrompido. Los 14 casos recuperaron un estado seguro y coherente.

## Compilar y comprobar el ejecutable

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm build_installer.spec
.\.venv\Scripts\python.exe scripts/check_exe_binaries.py
.\.venv\Scripts\python.exe scripts/smoke_release.py --exe dist/AudioDuplicateDetector.exe
```

El build_exe.bat actualizado utiliza dependencias fijadas, comprueba los códigos de salida y valida el paquete; ya no borra recursivamente las carpetas de compilación.

La validación no escribe resultados en el árbol del proyecto. También desactiva la caché de pytest y aísla `APPDATA`, `LOCALAPPDATA`, `TEMP` y `TMP`; esto evita bloqueos al finalizar cuando la instalación está dentro de una carpeta sincronizada por OneDrive.

## Límites y operación

- Los límites de candidatos pueden omitir coincidencias; la aplicación lo informa como cobertura incompleta. El contador de candidatos descartados cuenta apariciones, no necesariamente parejas únicas.
- Las pruebas sintéticas y de regresión no sustituyen una evaluación de precisión con música representativa ni pruebas prolongadas en NAS o bibliotecas masivas.
- La cancelación del scanner es cooperativa; puede esperar a que los trabajos ya iniciados terminen. Las operaciones de archivos no se interrumpen desde el diálogo para evitar dejar sincronizaciones a medias.
- No se añadieron servicios en la nube, telemetría, firma de código ni un actualizador automático.

## Resultado verificado en esta revisión

- Suite completa tras la corrección de buckets degenerados: **230 pruebas aprobadas y 11 subcasos aprobados**.
- Smoke test desde código: dos escaneos aprobados, incluida reutilización de caché y dry-run.
- Compilación PyInstaller: completada correctamente.
- Inspección del paquete: FFmpeg, FFprobe y fpcalc presentes; sin bases de datos.
- Smoke test del ejecutable con PATH restringido: tres escaneos aprobados, clasificación EXACT_AUDIO, detección espectral de transcode y archivos intactos.
- Auditoría de 30 dependencias: **0 vulnerabilidades conocidas reportadas por pip-audit**.
- Muestra controlada de cinco canciones reales y 20 casos derivados: **0 selecciones automáticas inseguras**; los originales de `F:\` no se modificaron.
- Pruebas de recuperación ante cierres y fallos: **14 de 14 casos aprobados**.

Los cambios de concurrencia, recall, análisis espectral empaquetado, etiquetas de interfaz, códigos de salida del CLI y evaluación integral se detallan en [THIRD_AUDIT_FIXES.md](THIRD_AUDIT_FIXES.md).
