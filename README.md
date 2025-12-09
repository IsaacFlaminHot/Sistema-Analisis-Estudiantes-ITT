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

## Testing

### Ejecutar tests localmente

```powershell
# Instalar dependencias de testing
pip install -r requirements.txt

# Ejecutar todos los tests
pytest

# Ejecutar tests con cobertura
pytest --cov=app --cov-report=html

# Ver reporte de cobertura
# Abre htmlcov/index.html en tu navegador
```

## Integración Continua (CI/CD)

Este proyecto utiliza **GitHub Actions** para implementar un pipeline de CI/CD completo que se ejecuta automáticamente en cada commit y pull request.

### Flujo de Trabajo del Pipeline

El pipeline de CI/CD está configurado en `.github/workflows/ci.yml` y ejecuta los siguientes jobs:

#### 1. **Tests Automatizados** (`test`)
- ✅ Ejecuta tests unitarios con `pytest`
- ✅ Prueba compatibilidad con Python 3.10, 3.11 y 3.12
- ✅ Genera reportes de cobertura de código
- ✅ Sube métricas de cobertura a Codecov

#### 2. **Análisis Estático - Pylint** (`lint`)
- 🔍 Analiza la calidad del código con Pylint
- 📊 Genera reportes detallados de problemas de código
- 📁 Guarda reportes como artefactos descargables

#### 3. **Análisis Estático - Flake8** (`flake8`)
- 🔍 Verifica el estilo y errores de código con Flake8
- 📊 Genera reportes HTML
- 📁 Guarda reportes como artefactos descargables

#### 4. **Análisis de Seguridad - Bandit** (`security`)
- 🔒 Escanea el código en busca de vulnerabilidades de seguridad
- 📊 Genera reportes JSON y texto
- 📁 Guarda reportes como artefactos descargables

#### 5. **Verificación de Formato - Black** (`format-check`)
- ✨ Verifica que el código siga el formato estándar
- 🎨 Asegura consistencia en el estilo de código

### Herramientas de Análisis Estático Utilizadas

| Herramienta | Propósito | Configuración |
|------------|-----------|---------------|
| **Pylint** | Análisis completo de calidad de código | `.pylintrc` |
| **Flake8** | Verificación de estilo PEP 8 | `.flake8` |
| **Bandit** | Análisis de seguridad | `.bandit` |
| **Black** | Formateo automático de código | `pyproject.toml` |
| **Pytest** | Framework de testing | `pytest.ini` |

### Ver Resultados del CI/CD

1. **En GitHub:**
   - Ve a la pestaña **"Actions"** en el repositorio
   - Selecciona el workflow que quieres ver
   - Revisa los logs de cada job

2. **Descargar Reportes:**
   - En la página del workflow, desplázate hasta la sección **"Artifacts"**
   - Descarga los reportes de Pylint, Flake8 y Bandit

3. **Ver Cobertura:**
   - Los reportes de cobertura están disponibles en formato HTML
   - También se pueden ver en Codecov si está configurado

### Ejecutar Análisis Localmente

```powershell
# Pylint
pylint app/ tests/

# Flake8
flake8 app/ tests/

# Bandit (seguridad)
bandit -r app/

# Black (verificar formato)
black --check app/ tests/

# Black (aplicar formato)
black app/ tests/
```

### Configuración de Archivos

- **`.pylintrc`**: Configuración de Pylint (reglas, límites, etc.)
- **`.flake8`**: Configuración de Flake8 (longitud de línea, ignorar errores)
- **`.bandit`**: Configuración de Bandit (niveles de confianza y severidad)
- **`pyproject.toml`**: Configuración de Black y Pytest
- **`pytest.ini`**: Configuración adicional de Pytest

### Resultados Esperados

Al ejecutar el pipeline, deberías ver:

- ✅ **Tests pasando** en todas las versiones de Python soportadas
- 📊 **Reportes de cobertura** mostrando qué porcentaje del código está cubierto
- 🔍 **Análisis estático** identificando problemas potenciales
- 🔒 **Análisis de seguridad** detectando vulnerabilidades
- ✨ **Verificación de formato** asegurando consistencia

### Mejores Prácticas

1. **Antes de hacer commit:**
   ```powershell
   # Ejecuta tests localmente
   pytest
   
   # Verifica formato
   black --check app/ tests/
   
   # Revisa problemas de código
   flake8 app/ tests/
   ```

2. **Si el pipeline falla:**
   - Revisa los logs en GitHub Actions
   - Descarga los reportes de artefactos
   - Corrige los problemas identificados
   - Haz commit de las correcciones

3. **Mantener alta cobertura:**
   - Añade tests para nuevas funcionalidades
   - Objetivo: >80% de cobertura de código
   - Revisa reportes de cobertura regularmente

### Documentación Completa

Para más detalles sobre el pipeline de CI/CD, consulta la [Documentación Completa de CI/CD](docs/CI_CD_DOCUMENTATION.md).

### Cambio de prueba para CI

Este bloque se agregó para validar que el pipeline de GitHub Actions se ejecute correctamente tras un commit de prueba.
