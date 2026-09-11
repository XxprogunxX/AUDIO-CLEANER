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

- Suite completa: **238 pruebas aprobadas y 11 subcasos parametrizados aprobados**.
- Reproducciones de los ocho síntomas observables de la auditoría: **0 fallas reproducidas** después de la corrección.
- Smoke test desde código: tres escaneos, cuatro archivos, caché y simulación aprobados; transcode lossless sospechoso detectado.
- Ejecutable PyInstaller reconstruido e inspeccionado: FFmpeg, FFprobe y Chromaprint incluidos; ninguna base de datos de usuario incluida.
- Smoke test del ejecutable con PATH restringido: clasificación `EXACT_AUDIO`, evaluación `suspected_transcode` y archivos intactos.
- Prueba aislada de espectro empaquetado: el ejecutable y el código fuente obtuvieron `suspected_transcode` y un corte de 14448.8 Hz sobre el mismo fixture.

## Límites que aún requieren evidencia de campo

El evaluador ya mide recall del pipeline completo, pero una cifra representativa necesita un corpus etiquetado de música real. Las coincidencias acústicas siguen exigiendo revisión humana y no reciben borrado automático. La distribución tampoco tiene firma Authenticode porque requiere un certificado de publicación controlado por el propietario.

## Corrección posterior: buckets acústicos degenerados

La indexación ya no genera tokens acústicos para huellas largas con menos de ocho palabras distintas, porque esa señal no permite discriminar pistas con fiabilidad. Los buckets que superan 500 miembros dejaron de truncarse por orden de ruta: ahora todos sus miembros participan en vecindarios dispersos, deterministas y acotados, ordenados por duración y proyecciones gruesas de la huella. Los tokens raros se procesan primero y la evidencia de buckets saturados necesita más corroboración.

El filtro de diferencia de duración de 90 segundos se aplica antes de enviar pares a los workers. La cobertura registra cuántos pares descartó ese filtro y cuántas huellas carecían de información suficiente. En la reproducción adversaria de 1,000 pistas, el caso pasó de 124,750 comparaciones a **0 comparaciones en 0.23 segundos**. Una prueba separada confirmó que una pareja situada después del antiguo límite de 500 sí llega al comparador, con menos de 5,000 comparaciones totales para 520 pistas.

## Corrección posterior: espera prolongada al agrupar bibliotecas reales

La caché real de 44,207 pistas mostró 4,653 parejas con el mismo hash PCM inicial y duración compatible. La versión anterior verificaba esas posibles equivalencias leyendo ambos audios completos de forma serial y sin actualizar la interfaz. Ahora calcula una identidad SHA-256 del PCM nativo completo una sola vez por archivo necesario, con hasta seis trabajos concurrentes, guarda únicamente resultados válidos en `pcm_identity_cache` y los reutiliza por el SHA-256 inmutable del archivo. La clasificación `EXACT_AUDIO` mantiene las restricciones de canales, layout, sample rate, bit depth y codec aplicables.

La indexación también usa una muestra temporal uniforme de palabras Chromaprint junto con los hashes tolerantes existentes. En las 44,088 huellas reales, las entradas estimadas bajaron de 26,547,283 a 4,909,890 (**81.5 % menos**). Un benchmark de solo lectura sobre la caché completa llegó a la comparación acústica en 36.4 segundos, incluyendo carga, agrupación exacta, construcción del índice y filtrado; la interfaz muestra avance separado para identidad PCM, indexación de huellas, filtrado de tokens y comparación de pares. La primera ejecución debe completar la nueva caché PCM; las siguientes la reutilizan.

## Corrección posterior: diagnóstico de cobertura

El aviso de cobertura confundía combinaciones teóricas de tokens acústicos saturados con candidatos reales omitidos. En la caché de 44,207 pistas, el contador mostraba 3,217,007 aunque los 12,533 candidatos legítimos se conservaron y ninguno alcanzó el límite de memoria. Esas métricas ahora están separadas: `candidate_pairs_dropped` representa únicamente candidatos rechazados por el tope de memoria, mientras `ambiguous_pair_occurrences_ignored` registra evidencia no discriminante y el filtro de duración conserva su propio contador.

El descubrimiento también excluye las carpetas técnicas de Windows antes de recorrerlas. Los archivos vacíos se registran como inválidos ignorados, y los fallos reales conservan ruta y motivo para mostrarlos en la interfaz. En la biblioteca examinada, los 31 supuestos fallos correspondían a 14 errores dentro de carpetas protegidas, 15 archivos de 0 bytes y solo 2 MP3 con acceso denegado.
