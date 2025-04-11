# simulation_examples/simulation_experiment_01.py # O como prefieras llamarlo

# Importar las clases de configuración y ejecución desde core
# ASUME que runner.py está en core/simulation/runner.py
from core.simulation.runner import SimulationRunner, ExperimentConfig
# Estas importaciones son necesarias si descomentas el bloque 4 opcional
# import os
# import pandas as pd

# --- PUNTO DE ENTRADA PRINCIPAL ---
if __name__ == "__main__":

    # ===> 1. Definir la Configuración del Experimento <===
    #    Un usuario nuevo SOLO necesita modificar esta sección.
    config = ExperimentConfig(
        # --- Personaliza tu experimento aquí ---
        mpp_file_name="Software Development Plan.mpp", # Archivo en data/
        num_simulations=5, # Número de ejecuciones
        resources_definition=[ # Define los recursos a usar
            # CORREGIDO: Usar "resource_id" como clave
            {"resource_id": 1, "name": "Dev Jr", "cost_per_hour": 30.0},
            {"resource_id": 2, "name": "Dev Mid", "cost_per_hour": 45.0},
            {"resource_id": 3, "name": "Dev Sr", "cost_per_hour": 60.0},
            {"resource_id": 4, "name": "QA", "cost_per_hour": 35.0}
        ],
        simulation_params={ # Ajusta los parámetros de simulación
            "error_margin": 0.20,   # Aumentar margen de error
            "reassignment_frequency": 10, # Reasignar cada 10 pasos
            "max_steps": 600         # Más pasos máximos
        },
        output_filename_base="experimento_simple_resultados", # Nombre del archivo de salida
        add_timestamp_to_filename=False, # Sobrescribir archivo de salida
        print_last_run_summary=True      # Mostrar resumen al final
        # --- Fin de la personalización ---
    )

    # ===> 2. Crear el Ejecutor de Simulaciones <===
    #    Se le pasa la configuración completa.
    try:
        runner = SimulationRunner(config=config)
        print(f"SimulationRunner creado para '{config.output_filename_base}'.")
    except Exception as e:
        print(f"Error Fatal: No se pudo crear SimulationRunner: {e}")
        exit(1) # Salir si el runner no se puede inicializar


    # ===> 3. Ejecutar las Simulaciones <===
    #    Esta única línea hace todo el trabajo pesado.
    try:
        print("Iniciando runner.run()...")
        runner.run()
        print("runner.run() finalizado.")
    except Exception as e:
        print(f"Error Fatal: Ocurrió un error durante la ejecución de runner.run(): {e}")
        import traceback
        traceback.print_exc() # Imprime el traceback detallado para depuración
        exit(1) # Salir si la ejecución falla


    # ===> 4. (Opcional) Acceder a los resultados AGREGADOS si es necesario ===
    #    (Descomenta si quieres hacer análisis extra aquí)
    '''
    # Necesitarías importar pandas y os arriba si descomentas esto
    results_df = runner.get_results()
    if results_df is not None:
        print("\nPrimeras 5 filas de resultados agregados:")
        print(results_df.head())
        # Ejemplo: Calcular costo final promedio
        # avg_final_cost = results_df.loc[results_df.groupby('simulation_id')['Time'].idxmax()]['ActualCost'].mean()
        # print(f"Costo final promedio: {avg_final_cost:.2f}")
    '''

    print("\nScript de experimento finalizado.")
    # El bloque opcional está comentado con ''' y correctamente indentado.