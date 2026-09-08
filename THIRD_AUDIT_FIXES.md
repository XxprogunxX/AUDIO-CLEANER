# Correcciones de la tercera auditoría — septiembre de 2026

Los siete hallazgos de la tercera auditoría quedaron corregidos y cubiertos por pruebas de regresión. Esta revisión no modificó la biblioteca musical de `F:\`.

## Cambios aplicados

1. **Backup y recuperación conservadores.** Una operación solo elimina su archivo temporal privado. Nunca borra ni sobrescribe un destino final ocupado o de pertenencia ambigua; esos archivos se preservan para revisión.
2. **Origen protegido contra carreras.** El servicio reclama el origen mediante un cambio de nombre atómico y mantiene un handle de Windows que impide escrituras concurrentes durante la operación. Si aparece un archivo nuevo con el nombre original, se conserva junto con el reclamo recuperable y la operación falla de forma segura.
3. **Mayor cobertura acústica.** La generación de candidatos conserva los tokens exactos anteriores y añade hashes difusos por segmentos para huellas suficientemente diversas. Los límites de memoria y candidatos siguen siendo estrictos.
4. **Análisis espectral autónomo.** El analizador resuelve FFmpeg mediante el mismo mecanismo que el resto de la aplicación, incluido el binario empaquetado, y termina todo el árbol del proceso ante timeout.
5. **Evidencia honesta en la interfaz.** Un FLAC sin medición ya no se presenta como auténtico. La interfaz distingue contenedor lossless, ausencia de indicios lossy y resultado no determinado. Cuando no hay medición espectral muestra ese estado y no dibuja barras sintéticas.
6. **CLI fiable para automatización.** La aplicación devuelve código distinto de cero ante carpeta inválida, escaneo incompleto u operación de archivos fallida, y siempre cierra la base de datos.
7. **Evaluación del pipeline completo.** `scripts/evaluation_runner.py --mode pipeline` mide si los archivos terminan juntos en los grupos finales y reporta TP, FP, TN, FN, recall, precisión, errores y cobertura.

## Evidencia de aceptación

- Suite completa: **227 pruebas aprobadas y 11 subcasos parametrizados aprobados**.
- Reproducciones de los ocho síntomas observables de la auditoría: **0 fallas reproducidas** después de la corrección.
- Smoke test desde código: tres escaneos, cuatro archivos, caché y simulación aprobados; transcode lossless sospechoso detectado.
- Ejecutable PyInstaller reconstruido e inspeccionado: FFmpeg, FFprobe y Chromaprint incluidos; ninguna base de datos de usuario incluida.
- Smoke test del ejecutable con PATH restringido: clasificación `EXACT_AUDIO`, evaluación `suspected_transcode` y archivos intactos.
- Prueba aislada de espectro empaquetado: el ejecutable y el código fuente obtuvieron `suspected_transcode` y un corte de 14448.8 Hz sobre el mismo fixture.

## Límites que aún requieren evidencia de campo

El evaluador ya mide recall del pipeline completo, pero una cifra representativa necesita un corpus etiquetado de música real. Las coincidencias acústicas siguen exigiendo revisión humana y no reciben borrado automático. La distribución tampoco tiene firma Authenticode porque requiere un certificado de publicación controlado por el propietario.
