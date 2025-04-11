# core/simulation/runner.py
import os
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import traceback # Para manejo de errores detallado

# --- Importaciones Absolutas desde CORE ---
# Asume que la carpeta raíz 'abp_simulator_mesa' está en el PYTHONPATH
# o que se ejecuta de forma que 'core' es reconocible.
try:
    from core.project import Project
    from core.entities import Resource
    from core.simulation.model import ProjectManagementModel # Modelo Mesa
    from core.simulation.parameters import SimulationParameters
    from core.readers.base_reader import ProjectReader # Base abstracta
    from core.readers.aspose_reader import AsposeProjectReader
    from core.readers.mpxj_reader import MpxjProjectReader
except ImportError as e:
     print(f"Error Fatal: No se pudieron importar componentes desde 'core' o 'core/readers': {e}")
     print("Asegúrate de que el proyecto se ejecute desde la raíz, que 'core' esté en PYTHONPATH,")
     print("y que existan los archivos __init__.py y los archivos de lectores en core/readers/.")
     # Salir si las importaciones base fallan
     raise e
# --- Fin Importaciones ---


@dataclass
class ExperimentConfig:
    """Define configuración para un experimento de simulación."""
    # Entradas
    mpp_file_name: str = "Software Development Plan.mpp" # Puede ser .mpx, .xml con MPXJ
    data_folder_relative_path: str = "data" # Relativo a la raíz del proyecto
    # Elegir lector: "aspose" o "mpxj"
    reader_type: str = "aspose"

    # Definición de Recursos (Clave es 'resource_id')
    resources_definition: List[Dict[str, Any]] = field(default_factory=lambda: [
        {"resource_id": 1, "name": "Developer_Jr", "cost_per_hour": 30.0},
        {"resource_id": 2, "name": "Developer_Mid", "cost_per_hour": 45.0},
        {"resource_id": 3, "name": "Developer_Sr", "cost_per_hour": 60.0},
        {"resource_id": 4, "name": "QA_Tester", "cost_per_hour": 35.0},
    ])

    # Parámetros Simulación (deben coincidir con SimulationParameters)
    simulation_params: Dict[str, Any] = field(default_factory=lambda: {
        "error_margin": 0.15, "reassignment_frequency": 7, "max_steps": 500
    })
    # Configuración Ejecución y Salida
    num_simulations: int = 10
    # Relativo a la raíz del proyecto detectada
    output_folder_relative_path: str = "core/generated"
    output_filename_base: str = "simulation_results_mesa"
    add_timestamp_to_filename: bool = False
    print_last_run_summary: bool = True


class SimulationRunner:
    """Orquesta ejecuciones de simulación usando un modelo basado en Mesa."""
    def __init__(self, config: ExperimentConfig):
        if not isinstance(config, ExperimentConfig):
            raise TypeError("El argumento 'config' debe ser una instancia de ExperimentConfig")
        self.config = config
        self.project_base: Optional[Project] = None
        self.simulation_params: Optional[SimulationParameters] = None
        self.aggregated_results: Optional[pd.DataFrame] = None
        self._project_root = self._detect_project_root()
        # Preparar rutas una vez al inicio, manejar error si falla
        try:
             self._setup_paths()
        except Exception as e:
             print(f"Error Fatal configurando rutas iniciales: {e}")
             raise

    def _detect_project_root(self) -> str:
        """Intenta detectar la carpeta raíz del proyecto."""
        try:
            # Asume __file__ está en core/simulation/runner.py -> ../.. llega a la raíz
            current_dir = os.path.dirname(__file__)
            root_path = os.path.normpath(os.path.join(current_dir, "..", ".."))
            # Verificación buscando 'core' y 'data'
            if os.path.isdir(os.path.join(root_path, 'core')) and os.path.isdir(os.path.join(root_path, 'data')):
                 return root_path
        except NameError: pass # __file__ no definido
        cwd = os.getcwd()
        print(f"Advertencia (Runner): No se pudo auto-detectar raíz. Usando dir actual: {cwd}")
        return cwd

    def _setup_paths(self):
        """Construye y valida rutas basado en config y raíz detectada."""
        # Ruta Archivo de Entrada (MPP, MPX, XML...)
        self.input_project_file_path = os.path.join(self._project_root, self.config.data_folder_relative_path, self.config.mpp_file_name) # Renombrar variable
        self.input_project_file_path = os.path.normpath(self.input_project_file_path)
        if not os.path.exists(self.input_project_file_path):
            raise FileNotFoundError(f"Archivo de entrada no encontrado: {self.input_project_file_path}")

        # Ruta Salida CSV
        self.output_dir = os.path.join(self._project_root, self.config.output_folder_relative_path)
        self.output_dir = os.path.normpath(self.output_dir)
        output_filename = f"{self.config.output_filename_base}.csv"
        if self.config.add_timestamp_to_filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"{self.config.output_filename_base}_{timestamp}.csv"
        self.output_filepath = os.path.join(self.output_dir, output_filename)
        try:
            os.makedirs(self.output_dir, exist_ok=True)
        except OSError as e:
            raise OSError(f"No se pudo crear directorio de salida '{self.output_dir}': {e}")

    def _prepare_project_and_params(self):
        """Selecciona lector, carga proyecto, añade recursos config, prepara params."""
        print(f"Info (Runner): Preparando proyecto desde '{self.input_project_file_path}'...")

        # --- Seleccionar y Crear Lector ---
        reader: Optional[ProjectReader] = None
        reader_choice = self.config.reader_type.lower()
        print(f"Info (Runner): Usando lector tipo '{reader_choice}'...")

        if reader_choice == "aspose":
            reader = AsposeProjectReader()
        elif reader_choice == "mpxj":
            try:
                 # La inicialización de MpxjReader asegura JVM y carga clases Java
                 reader = MpxjProjectReader()
            except (FileNotFoundError, RuntimeError, ImportError) as mpxj_e:
                 print(f"Error Fatal: No se pudo inicializar MPXJReader: {mpxj_e}")
                 print("Verifica la ruta al JAR de MPXJ en MpxjProjectReader, instalación Java y JPype.")
                 raise mpxj_e # Detener si MPXJ no está listo
        else:
            raise ValueError(f"Tipo de lector desconocido: '{self.config.reader_type}'. Usar 'aspose' o 'mpxj'.")

        # Cargar proyecto usando el lector seleccionado
        # Esto puede lanzar FileNotFoundError, ValueError, etc.
        self.project_base = reader.load(self.input_project_file_path)
        # --- Fin Selección y Uso Lector ---

        if not self.project_base or not self.project_base.tasks:
             raise ValueError("El lector no devolvió un proyecto válido con tareas.")
        print(f"Info (Runner): Proyecto '{self.project_base.project_name}' cargado ({len(self.project_base.tasks)} tareas).")

        # --- Añadir recursos definidos en la CONFIGURACIÓN ---
        # (Estos pueden complementar o reemplazar los leídos del archivo)
        num_resources_added_from_config = 0
        # Opción: Limpiar los leídos del archivo y usar solo los de config
        # self.project_base.resources = {}
        print(f"Info (Runner): Añadiendo/Sobrescribiendo {len(self.config.resources_definition)} recursos desde ExperimentConfig...")
        for res_data in self.config.resources_definition:
             try:
                 # Usar **res_data (espera 'resource_id' en config)
                 res = Resource(**res_data)
                 self.project_base.add_resource(res) # add_resource maneja si ya existe
                 num_resources_added_from_config += 1
             except (TypeError, KeyError, ValueError) as e:
                 print(f"Advertencia (Runner): Ignorando def. de recurso inválida {res_data}: {e}")

        if num_resources_added_from_config == 0 and not self.project_base.resources:
             # Error solo si NO hay recursos ni del archivo NI de config
             raise ValueError("No hay recursos válidos disponibles (ni de archivo ni de config).")
        elif num_resources_added_from_config > 0:
             print(f"Info (Runner): {num_resources_added_from_config} recursos de config aplicados (Total ahora: {len(self.project_base.resources)}).")
        elif self.project_base.resources:
             # Esto se imprimiría si config.resources_definition está vacío pero el archivo sí tenía recursos
             print(f"Info (Runner): Usando {len(self.project_base.resources)} recursos cargados del archivo (ninguno definido en config).")


        # Preparar parámetros de simulación (sin cambios)
        try:
            self.simulation_params = SimulationParameters(**self.config.simulation_params)
            print(f"Info (Runner): Parámetros de simulación listos: {self.simulation_params}")
        except TypeError as e: raise TypeError(f"Parámetros inválidos en config: {e}")


    def run(self):
        """Ejecuta el conjunto completo de simulaciones usando el modelo Mesa."""
        print(f"\n--- Iniciando {self.config.num_simulations} Simulaciones ({self.config.reader_type.upper()}) ---")
        all_simulation_data = []
        last_run_data: Optional[pd.DataFrame] = None

        try:
            self._prepare_project_and_params()
            print(f"Info (Runner): Preparación completada. Ejecutando simulaciones...")
        except Exception as e:
            print(f"Error Fatal en la fase de preparación: {e}")
            traceback.print_exc()
            return

        for sim_id in range(1, self.config.num_simulations + 1):
            # if self.config.num_simulations > 1: print(f"--- Sim {sim_id}/{self.config.num_simulations} ---") # Opcional
            try:
                # Crear el modelo Mesa para esta simulación
                model = ProjectManagementModel(self.project_base, self.simulation_params)
            except Exception as e:
                print(f"Error Fatal creando modelo (Sim {sim_id}): {e}")
                traceback.print_exc(); return

            # Ejecutar el modelo Mesa por N pasos
            max_steps = self.simulation_params.max_steps
            final_step_count = 0
            try:
                for _ in range(max_steps):
                    if hasattr(model, 'running') and not model.running: break
                    model.step()
                final_step_count = model.schedule.steps # Registrar pasos reales
            except Exception as e:
                 print(f"Error durante ejecución de pasos (Sim {sim_id}): {e}")
                 traceback.print_exc(); continue # Saltar simulación

            # Recoger datos del DataCollector del modelo
            try:
                if hasattr(model, 'datacollector') and model.datacollector:
                    report_df = model.datacollector.get_model_vars_dataframe()
                    if not report_df.empty:
                        report_df['simulation_id'] = sim_id
                        all_simulation_data.append(report_df)
                        last_run_data = report_df
            except Exception as e: print(f"Error recogiendo datos (Sim {sim_id}): {e}")

        # --- Fin Bucle de Simulaciones ---
        print(f"--- {self.config.num_simulations} Simulaciones Terminadas ---")

        if all_simulation_data:
            self.aggregated_results = pd.concat(all_simulation_data, ignore_index=True)
            cols = ['simulation_id'] + [c for c in self.aggregated_results if c != 'simulation_id']
            self.aggregated_results = self.aggregated_results.reindex(columns=cols, fill_value=None)
            print(f"Info (Runner): Resultados agregados generados ({len(self.aggregated_results)} filas).")
            self.save_results()
            if self.config.print_last_run_summary and last_run_data is not None:
                self._show_run_summary(last_run_data)
        else: print("Advertencia (Runner): No se generaron datos agregados.")


    def get_results(self) -> Optional[pd.DataFrame]:
        return self.aggregated_results

    def save_results(self, output_filepath: Optional[str] = None):
        if self.aggregated_results is None or self.aggregated_results.empty:
            print("Adv (Runner): No hay resultados agregados para guardar."); return
        if output_filepath is None: output_filepath = self.output_filepath
        try:
            output_dir = os.path.dirname(output_filepath); os.makedirs(output_dir, exist_ok=True)
            self.aggregated_results.to_csv(output_filepath, index=False)
            print(f"Info (Runner): Resultados agregados guardados en '{output_filepath}'.")
        except Exception as e: print(f"Error (Runner): Falló al guardar resultados en '{output_filepath}': {e}"); traceback.print_exc()

    def _show_run_summary(self, report_df: pd.DataFrame):
        print("\n--- Resumen Sim (Última Ejecución) ---")
        if report_df is None or report_df.empty: print("No hay datos."); return
        try:
            last = report_df.iloc[-1]; time, comp, ev, ac, cpi = 'Time', 'Completion', 'EarnedValue', 'ActualCost', 'CPI'
            req = [time, comp, ev, ac, cpi]
            if not all(c in last.index for c in req): print(f"Error: Faltan cols: {req}. Encontradas: {last.index.tolist()}"); return
            cpi_v = last[cpi]; cpi_s = "Inf" if cpi_v == float('inf') else ("0.00/NA" if pd.isna(cpi_v) or abs(cpi_v) < 1e-9 else f"{cpi_v:.2f}")
            print(f"Pasos: {last[time]}, Compl: {last[comp]:.2f}%, EV: {last[ev]:.2f}, AC: {last[ac]:.2f}, CPI: {cpi_s}")
        except Exception as e: print(f"Error resumen: {e}"); traceback.print_exc()
        print("-" * 36)