# ABP Simulator - Prototipo Web

Este repositorio contiene el prototipo web del simulador de proyectos ABP (Aprendizaje Basado en Proyectos).

## Cómo Obtener el Prototipo

### Opción 1: Descargar ZIP
1. Ve a https://github.com/FRQ23/gradflow
2. Haz clic en el botón verde "Code"
3. Selecciona "Download ZIP"
4. Extrae el archivo ZIP en tu computadora

### Opción 2: Clonar el Repositorio
```bash
git clone https://github.com/FRQ23/gradflow.git
```

## Cómo Ver el Prototipo

1. Navega a la carpeta `prototipo_web`
2. Haz doble clic en `index.html` para abrir en tu navegador predeterminado

## Estructura del Prototipo

El prototipo consta de tres páginas principales:

1. **Configuración** (`index.html`)
   - Carga de archivos XML
   - Configuración de parámetros de simulación
   - Inicio de la simulación

2. **Dashboard** (`dashboard.html`)
   - Visualización en tiempo real
   - Control de la simulación
   - Métricas actuales

3. **Reporte** (`report.html`)
   - Resultados finales
   - Gráficos de distribución
   - Exportación de datos

## Navegación

1. Comienza en `index.html`
2. Configura los parámetros de simulación
3. Inicia la simulación para ir al dashboard
4. Al finalizar, verás el reporte de resultados

## Requisitos Técnicos

- Navegador web moderno (Chrome, Firefox, Edge, Safari)
- JavaScript habilitado
- Conexión a internet (para cargar Bootstrap y Chart.js)

## Notas Importantes

- Este es un prototipo frontend, por lo que algunas funcionalidades son simuladas
- Los datos mostrados son de ejemplo
- La exportación de datos está deshabilitada en el prototipo

## Estructura de Archivos

```
prototipo_web/
├── index.html          # Página de configuración
├── dashboard.html      # Panel de control
├── report.html         # Resultados
├── css/
│   ├── style.css      # Estilos personalizados
│   └── bootstrap.min.css
├── js/
│   └── main.js        # Lógica de la aplicación
└── assets/            # Recursos (imágenes, etc.)
```

## Soporte

Si encuentras algún problema al visualizar el prototipo, asegúrate de:
1. Tener JavaScript habilitado en tu navegador
2. Usar un navegador actualizado
3. Tener conexión a internet para cargar las dependencias 