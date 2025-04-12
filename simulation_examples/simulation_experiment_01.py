# simulation_examples/simulation_experiment_01.py
"""
Ejemplo Simplificado de Ejecución de Simulación.
------------------------------------------------
Este script configura y ejecuta una simulación de gestión de proyectos.
Modifica los valores en la sección '--- CONFIGURACIÓN DEL EXPERIMENTO ---'
para ajustar la simulación a tus necesidades.
"""
import sys
import os
import traceback # Aunque runner maneja errores, útil si falla el import inicial

# --- Configuración del Entorno (Importante para encontrar 'core') ---
# Añadir el directorio raíz del proyecto al PYTHONPATH
# Asume que este script está en 'simulation_examples' y 'core' está en la raíz
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.normpath(os.path.join(current_dir, '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# --- Fin Configuración del Entorno ---

# --- Importar Componentes Esenciales ---
try:
    from core.simulation.runner import ExperimentConfig, SimulationRunner
except ImportError:
    print("Error Fatal: No se pudo importar 'ExperimentConfig' o 'SimulationRunner'.")
    print(f"Verifica que sys.path incluye la raíz del proyecto ('{project_root}') y la estructura es correcta.")
    traceback.print_exc()
    sys.exit(1) # Salir si no se puede importar lo esencial
# --- Fin Importar Componentes ---


# --- CONFIGURACIÓN DEL EXPERIMENTO ---
# Este es el ÚNICO bloque que un usuario debería necesitar modificar normalmente.

experiment_settings = ExperimentConfig(
    # --- Archivo de Entrada y Lector ---
    mpp_file_name="Software Development Plan.xml",  # Archivo de proyecto (ej. .xml, .mpp)
    data_folder_relative_path="data",             # Carpeta (relativa a la raíz) donde está el archivo
    reader_type="xml",                            # Lector: "xml", "mpxj", "aspose"

    # --- Parámetros Clave de la Simulación ---
    simulation_params={
        "error_margin": 0.1,        # Margen +/- en la duración/trabajo de tareas
        "reassignment_frequency": 0,  # Frecuencia de reasignación de tareas (0 = nunca)
        "max_steps": 3000             # Límite de pasos (días/horas simulados)
    },

    # --- Configuración de la Ejecución ---
    num_simulations=5,                            # Número de ejecuciones Monte Carlo
    output_filename_base="sim_sdp_results_v2",    # Nombre base para el archivo CSV de salida
    add_timestamp_to_filename=True,               # Añadir fecha/hora al nombre del archivo CSV?
    output_folder_relative_path="core/generated", # Carpeta (relativa a la raíz) para guardar CSV

    # --- Opciones de Visualización en Consola ---
    show_loaded_tasks=True,      # Mostrar lista de tareas al inicio? (True/False)
    show_loaded_resources=True,  # Mostrar lista de recursos/agentes al inicio? (True/False)
    display_limit=15,             # Límite de ítems a mostrar si las opciones anteriores son True
    print_last_run_summary=True,  # Mostrar resumen de EVM al final? (True/False)

    # --- (Avanzado) Definición de Costos de Recursos ---
    # Útil si el archivo de proyecto no tiene costos o quieres probar otros.
    # Formato: [{'resource_id': ID_RECURSO, 'cost_per_hour': COSTO}, ...]
    # Déjalo vacío `[]` para usar los costos del archivo de proyecto.
    resources_definition=[]
    # Ejemplo: resources_definition=[{'resource_id': 4, 'cost_per_hour': 30.0}] # Cambiar costo del Developer
)

# --- FIN DE LA CONFIGURACIÓN ---


# --- EJECUCIÓN DE LA SIMULACIÓN ---
# Esta parte no necesita ser modificada por el usuario.

print("=" * 70)
print(" Ejecutando Experimento de Simulación de Gestión de Proyectos ")
print("=" * 70)
print(f"Configuración:")
print(f"  - Archivo Proyecto : {experiment_settings.mpp_file_name} (en {experiment_settings.data_folder_relative_path}/)")
print(f"  - Lector Usado     : {experiment_settings.reader_type.upper()}")
print(f"  - Simulaciones     : {experiment_settings.num_simulations}")
print(f"  - Parámetros Sim   : {experiment_settings.simulation_params}")
print("-" * 70)

# 1. Crear el Runner con la configuración definida
#    El Runner se encargará de toda la lógica interna.
runner = SimulationRunner(config=experiment_settings)

# 2. Ejecutar el proceso completo.
#    El método .run() encapsula la preparación, ejecución,
#    manejo de errores principales, guardado de resultados y limpieza.
runner.run()

# 3. Fin del script.
#    Los resultados (si se generaron) están en el archivo CSV indicado
#    en la configuración y mostrado en los logs del runner.
#    El runner también imprime un resumen si se configuró.

print("\n" + "=" * 70)
print(" Script de Experimento Finalizado. ")
print(f" Revisa los logs y el archivo CSV en: {experiment_settings.output_folder_relative_path} ")
print("=" * 70)