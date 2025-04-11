# simulation_examples/simulation_experiment_mpxj_01.py

# Importar las clases de configuración y ejecución desde core
try:
    # Asumiendo que runner.py está en core/simulation/
    from core.simulation.runner import SimulationRunner, ExperimentConfig
except ImportError as e:
    print(f"Error Fatal: No se pudo importar SimulationRunner/ExperimentConfig: {e}")
    exit(1)

# --- PUNTO DE ENTRADA PRINCIPAL ---
if __name__ == "__main__":

    # ===> 1. Definir la Configuración del Experimento <===
    config_mpxj = ExperimentConfig(
        # --- Personalización ---

        # *** USAR LECTOR MPXJ ***
        reader_type = "mpxj",

        # Archivo de entrada (puede ser .mpp, .mpx, .xml, etc. soportado por MPXJ)
        # Asegúrate que este archivo exista en la carpeta 'data/'
        mpp_file_name="Software Development Plan.mpp", # Puedes cambiarlo a un .mpx si tienes

        num_simulations=3, # Número de ejecuciones

        # Recursos para la simulación (estos se usan independientemente del lector)
        resources_definition=[
            {"resource_id": 1, "name": "MPXJ_Dev1", "cost_per_hour": 55.0},
            {"resource_id": 2, "name": "MPXJ_Dev2", "cost_per_hour": 55.0},
            {"resource_id": 3, "name": "MPXJ_QA", "cost_per_hour": 45.0}
        ],

        # Parámetros de la simulación
        simulation_params={
            "error_margin": 0.10,
            "reassignment_frequency": 0, # Sin reasignación
            "max_steps": 1000
        },

        # Configuración de salida
        output_filename_base="mpxj_experiment_results", # Nombre de archivo diferente
        add_timestamp_to_filename=True,
        print_last_run_summary=True
        # --- Fin de la personalización ---
    )

    # ===> 2. Crear el Ejecutor de Simulaciones <===
    try:
        runner = SimulationRunner(config=config_mpxj)
        print(f"SimulationRunner creado para '{config_mpxj.output_filename_base}' usando MPXJ.")
    except Exception as e:
        print(f"Error Fatal: No se pudo crear SimulationRunner: {e}")
        exit(1)

    # ===> 3. Ejecutar las Simulaciones <===
    try:
        print("Iniciando runner.run()... (usando MPXJ)")
        runner.run()
        print("runner.run() con MPXJ finalizado.")
    except Exception as e:
        print(f"Error Fatal durante la ejecución de runner.run() con MPXJ: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

    # ===> 4. (Opcional) Acceder a resultados <===
    # results_df = runner.get_results()
    # if results_df is not None:
    #     print("\nResultados agregados (MPXJ):")
    #     print(results_df.head())

    print("\nScript de experimento MPXJ finalizado.")