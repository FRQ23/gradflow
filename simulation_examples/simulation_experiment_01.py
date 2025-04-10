# simulation_examples/simulation_experiment_01.py

# Importar las clases de configuración y ejecución desde core
from core.simulation.runner import SimulationRunner, ExperimentConfig


# --- PUNTO DE ENTRADA PRINCIPAL ---
if __name__ == "__main__":

    # ===> 1. Definir la Configuración del Experimento <===
    config = ExperimentConfig(
        # --- Personaliza tu experimento aquí ---
        mpp_file_name="Software Development Plan.mpp", # Archivo en data/
        num_simulations=5, # Número de ejecuciones
        resources_definition=[ # Define los recursos a usar
            {"id": 1, "name": "Dev Jr", "cost_per_hour": 30.0},
            {"id": 2, "name": "Dev Mid", "cost_per_hour": 45.0},
            {"id": 3, "name": "Dev Sr", "cost_per_hour": 60.0},
            {"id": 4, "name": "QA", "cost_per_hour": 35.0}
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
    runner = SimulationRunner(config=config)

    # ===> 3. Ejecutar las Simulaciones <===
    #    Esto cargará datos, correrá los bucles, recogerá métricas y guardará resultados.
    runner.run()

'''
    # ===> 4. (Opcional) Acceder a los resultados si es necesario ===
    results_df = runner.get_results()  
    if results_df is not None:  
        print("\nPrimeras 5 filas de resultados agregados:")  # 
        print(results_df.head())  # 


    print("\nScript de experimento finalizado.")
    
'''