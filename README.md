# Sistema de registro y análisis de estudiantes (ITT)

Aplicación Flask para apoyar al docente a identificar, analizar y visualizar
reprobación y deserción. Permite autenticación de docente, registro/CRUD,
importación desde Excel, gráficas de calidad (Pareto, histograma, dispersión, Ishikawa resumido)
y exportación a CSV.

## Repositorio

Este proyecto está disponible en GitHub: [IsaacFlaminHot/Sistema-Analisis-Estudiantes-ITT](https://github.com/IsaacFlaminHot/Sistema-Analisis-Estudiantes-ITT)

## Requisitos
- Python 3.10+
- PowerShell (Windows)

## Instalación
```powershell
# Estar en el directorio del proyecto
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Crear un docente (opcional, desde la interfaz /auth/register)
python run.py
```

Visita `http://127.0.0.1:5000/`. Regístrate en `/auth/register` y luego inicia sesión.

## Importar Excel
- Hoja con columnas: `matricula, nombre, carrera, semestre, materia, nota, asistencia, periodo`
- Valores de `nota` y `asistencia` deben estar entre 0 y 100.
- Sube el archivo en `Datos -> Importar Excel`.

## Exportar
- `Datos -> Estudiantes -> Exportar CSV`

## Notas
- La base SQLite se crea automáticamente en `data.db` en la carpeta del proyecto.
- Para generar imágenes estáticas de gráficos podrías usar Kaleido; en esta versión los gráficos se renderizan en el navegador con Plotly.
