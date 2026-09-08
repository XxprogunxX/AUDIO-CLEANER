# Segunda auditoría de confiabilidad — septiembre de 2026

## Dictamen

La versión corregida queda como candidata de liberación para uso controlado. Las operaciones automáticas se limitan a identidad binaria (`EXACT_HASH`) o identidad completa del audio PCM (`EXACT_AUDIO`) y vuelven a validar los archivos justo antes de actuar. Las coincidencias acústicas siempre requieren revisión manual.

Este dictamen cubre el código, el paquete de Windows y pruebas controladas. No constituye una certificación formal ni demuestra precisión estadística sobre las 44 mil canciones completas.

## Hallazgos corregidos en esta etapa

1. **Coincidencias acústicas demasiado permisivas.** Chromaprint puede considerar muy parecidos dos archivos que comparten un fragmento largo aunque difieran en otras partes. Se eliminó toda selección automática en grupos `ACOUSTIC_DUPLICATE`.
2. **Backup sin revalidación previa.** Backup ahora rechaza un archivo si cambió desde el escaneo, igual que papelera y eliminación permanente.
3. **Copia interrumpida o dañada.** Backup escribe a un destino temporal privado, sincroniza, verifica SHA-256 y solo entonces publica la copia y retira el origen. El journal conserva ruta temporal y hash esperado para recuperar un cierre inesperado.
4. **Reconciliación ambigua.** Si el origen desapareció, únicamente un destino con el hash esperado permite completar la operación. Una copia dañada queda en fallo y conserva el registro de base de datos para revisión.
5. **Validación no aislada.** La suite ya no crea un reporte dentro del árbol del proyecto. El ejecutor de pruebas aísla el estado y desactiva la caché de pytest, que podía quedar bloqueada al sincronizarse en OneDrive.

## Evidencia ejecutada

| Comprobación | Resultado |
|---|---:|
| Suite automatizada completa | 218 aprobadas + 11 subcasos |
| Casos adversarios de precisión | 0 selecciones automáticas inseguras |
| Equivalencias exactas seleccionadas correctamente | 3 de 3 |
| Recuperación ante cierres/fallos | 14 de 14 |
| Muestra con música real copiada | 20 de 20 condiciones de seguridad |
| Dependencias analizadas con pip-audit | 30, sin vulnerabilidades conocidas reportadas |
| Smoke test del ejecutable empaquetado | Aprobado con PATH restringido |
| Binarios incluidos | FFmpeg, FFprobe y fpcalc presentes |
| Modificación de originales en `F:\` | Ninguna |

La muestra real tomó cinco canciones de carpetas diferentes y creó únicamente copias aisladas. Para cada origen se comprobó una copia exacta, una transcodificación MP3, una variante de volumen y un híbrido con contenido diferente después de 65 segundos. Solo las copias exactas quedaron seleccionadas automáticamente.

## Inventario de la biblioteca

El inventario de solo lectura localizó **44,196 archivos**, con **239,375,879,129 bytes (222.94 GiB)**:

| Formato | Archivos |
|---|---:|
| MP3 | 42,907 |
| WMA | 999 |
| M4A | 160 |
| WAV | 85 |
| FLAC | 45 |

Windows denegó lectura en cinco carpetas: `F:\huapangos nuevos`, `F:\musica nueva`, `F:\videos de navidad`, `F:\videos niños` y `F:\videos nuevos`. Esas carpetas no forman parte de las cifras ni de la muestra.

## Trabajo restante para una liberación profesional

1. **Prueba integral de la biblioteca.** Resolver los permisos de las cinco carpetas y ejecutar un escaneo completo de solo lectura sobre `F:\`. Conservar métricas de duración, errores, cobertura y consumo máximo de memoria.
2. **Ensayo operacional.** Revisar una muestra estratificada de resultados, ejecutar primero `dry-run` y después backup en lotes pequeños. Verificar restauración desde backup antes de autorizar una operación masiva.
3. **Firma digital.** El ejecutable actual no está firmado. Adquirir o proporcionar un certificado de firma de código, firmar con sello de tiempo y verificar la firma en una máquina limpia.
4. **Distribución repetible.** Generar un instalador versionado, publicar hashes SHA-256 y conservar los reportes de pruebas asociados a cada versión.
5. **Automatización de entrega.** Ejecutar pruebas, auditoría de dependencias, compilación, inspección del paquete y smoke test en cada cambio mediante integración continua.
6. **Calibración continua.** Crear un conjunto de referencia etiquetado con música representativa de la biblioteca. Medir falsos positivos y falsos negativos por formato, duración y tipo de edición antes de cambiar umbrales.

## Criterio de operación recomendado

Hasta terminar el escaneo integral y el ensayo de restauración, usar eliminación permanente únicamente en equivalencias exactas revisadas. Para el resto, usar backup o papelera por lotes y mantener revisión manual para toda coincidencia acústica.
