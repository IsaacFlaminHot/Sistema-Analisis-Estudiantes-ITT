# Sistema de registro y análisis de estudiantes (ITT)

Aplicación Flask para apoyar al docente a identificar, analizar y visualizar
reprobación y deserción. Permite autenticación de docente, registro/CRUD,
importación desde Excel, gráficas de calidad (Pareto, histograma, dispersión, Ishikawa resumido)
y exportación a CSV.

## Repositorio

Este proyecto está disponible en GitHub: [saacFlaminHot/Proyecto-Analisis-Estudiantil](https://github.com/saacFlaminHot/Proyecto-Analisis-Estudiantil)

## Requisitos
- Python 3.10+
- PowerShell (Windows)

## Instalaci 3n
```powershell
# Estar en el directorio del proyecto
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Crear un docente (opcional, desde la interfaz /auth/register)
python run.py
```

Visita `http://127.0.0.1:5000/`. Reg edstrate en `/auth/register` y luego inicia sesi 3n.

## Importar Excel
- Hoja con columnas: `matricula, nombre, carrera, semestre, materia, nota, asistencia, periodo`
- Valores de `nota` y `asistencia` deben estar entre 0 y 100.
- Sube el archivo en `Datos -> Importar Excel`.

## Exportar
- `Datos -> Estudiantes -> Exportar CSV`

## Notas
- La base SQLite se crea autom 1ticamente en `data.db` en la carpeta del proyecto.
- Para generar im genes est ticas de gr ficos podr as usar Kaleido; en esta versi 3n los gr ficos se renderizan en el navegador con Plotly.
