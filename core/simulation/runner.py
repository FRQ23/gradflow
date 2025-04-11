# core/simulation/runner.py
import os
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import traceback

# --- Importaciones Absolutas desde CORE ---
# Asume que la carpeta raíz 'abp_simulator_mesa' está en el PYTHONPATH
# o que se ejecuta de forma que 'core' es reconocible.
# Eliminamos el try/except, si esto falla, hay un problema de path fundamental.
from core.project import Project
from core.entities import Resource
from core.simulation.model import ProjectManagementModel # Modelo Mesa
from core.simulation.parameters import SimulationParameters
# --- Fin Importaciones ---


@dataclass
class ExperimentConfig:
    """Define configuración para un experimento de simulación."""
    # Entradas
    mpp_file_name: str = "Software Development Plan.mpp"
    data_folder_relative_path: str = "data"

    # Definición de Recursos
    # *** CORREGIDO: Clave es 'resource_id' ***
    resources_definition: List[Dict[str, Any]] = field(default_factory=lambda: [
        {"resource_id": 1, "name": "Developer_Jr", "cost_per_hour": 30.0},
        {"resource_id": 2, "name": "Developer_Mid", "cost_per_hour": 45.0},
        {"resource_id": 3, "name": "Developer_Sr", "cost_per_hour": 60.0},
        {"resource_id": 4, "name": "QA_Tester", "cost_per_hour": 35.0},
    ])

    # Parámetros Simulación
    simulation_params: Dict[str, Any] = field(default_factory=lambda: {
        "error_margin": 0.15, "reassignment_frequency": 7, "max_steps": 500
    })
    # Ejecución y Salida
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
        try:
             self._setup_paths()
        except Exception as e:
             print(f"Error Fatal configurando rutas iniciales: {e}")
             raise

    def _detect_project_root(self) -> str:
        # Intenta detectar la raíz (abp_simulator_mesa) subiendo dos niveles desde este archivo
        try:
            current_dir = os.path.dirname(__file__)
            # Asumiendo que este archivo está en core/simulation/
            root_path = os.path.normpath(os.path.join(current_dir, "..", ".."))
            # Verificar si parece ser la raíz correcta (contiene 'core' y 'data')
            if os.path.isdir(os.path.join(root_path, 'core')) and os.path.isdir(os.path.join(root_path, 'data')):
                 return root_path
        except NameError: pass # __file__ no definido
        cwd = os.getcwd()
        print(f"Advertencia (Runner): Usando directorio actual como raíz: {cwd}")
        return cwd

    def _setup_paths(self):
        """Construye y valida rutas."""
        # Ruta MPP (Basada en raíz detectada y config)
        self.input_mpp_path = os.path.join(self._project_root, self.config.data_folder_relative_path, self.config.mpp_file_name)
        self.input_mpp_path = os.path.normpath(self.input_mpp_path)
        if not os.path.exists(self.input_mpp_path):
            raise FileNotFoundError(f"Archivo MPP no encontrado: {self.input_mpp_path}")

        # Ruta Salida CSV (Basada en raíz detectada y config)
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
        """Carga proyecto, añade recursos, prepara parámetros."""
        print(f"Info (Runner): Preparando proyecto desde '{self.input_mpp_path}'...")
        self.project_base = Project()
        self.project_base.load_from_mpp(self.input_mpp_path)
        if not self.project_base.tasks:
             raise ValueError("El proyecto MPP cargado no contiene tareas de trabajo.")

        num_resources_added = 0
        for res_data in self.config.resources_definition:
             try:
                 # --- Usar **res_data (asegura que 'resource_id' esté en Config) ---
                 if "resource_id" not in res_data: # Validación extra
                      print(f"Advertencia (Runner): Falta 'resource_id' en {res_data}. Omitiendo.")
                      continue
                 # Intentar convertir cost_per_hour a float explícitamente
                 res_data['cost_per_hour'] = float(res_data['cost_per_hour'])
                 res = Resource(**res_data) # <-- Desempaquetado
                 self.project_base.add_resource(res)
                 num_resources_added += 1
             except (TypeError, KeyError, ValueError) as e:
                 print(f"Advertencia (Runner): Ignorando def. de recurso inválida {res_data}: {e}")

        if num_resources_added == 0:
             # Este es el error que se está viendo porque la creación falla antes
             raise ValueError("No se definieron o añadieron recursos válidos desde la configuración.")
        print(f"Info (Runner): {num_resources_added} recursos añadidos al proyecto base.")

        try:
            # Crear instancia de SimulationParameters
            self.simulation_params = SimulationParameters(**self.config.simulation_params)
            print(f"Info (Runner): Parámetros de simulación listos: {self.simulation_params}")
        except TypeError as e:
             raise TypeError(f"Parámetros de simulación inválidos en config: {e}")

    def run(self):
        """Ejecuta el conjunto completo de simulaciones."""
        print(f"\n--- Iniciando {self.config.num_simulations} Simulaciones ---")
        all_simulation_data = []
        last_run_data: Optional[pd.DataFrame] = None

        try:
            self._prepare_project_and_params()
            print(f"Info (Runner): Preparación completada. Ejecutando...")
        except Exception as e:
            print(f"Error Fatal en la fase de preparación: {e}")
            traceback.print_exc()
            return

        for sim_id in range(1, self.config.num_simulations + 1):
            # if self.config.num_simulations > 1: print(f"--- Sim {sim_id}/{self.config.num_simulations} ---")
            try:
                model = ProjectManagementModel(self.project_base, self.simulation_params)
            except Exception as e:
                print(f"Error Fatal creando modelo (Sim {sim_id}): {e}")
                traceback.print_exc()
                return # Detener si el modelo no se crea

            max_steps = self.simulation_params.max_steps
            final_step_count = 0
            try:
                for current_step in range(max_steps):
                    if hasattr(model, 'running') and not model.running: break
                    model.step()
                    final_step_count = model.schedule.steps
            except Exception as e:
                 print(f"Error durante ejecución (Sim {sim_id}, Step ~{current_step+1}): {e}")
                 traceback.print_exc()
                 continue # Saltar a siguiente simulación

            # Recoger datos
            try:
                if hasattr(model, 'datacollector') and model.datacollector:
                    report_df = model.datacollector.get_model_vars_dataframe()
                    if not report_df.empty:
                        report_df['simulation_id'] = sim_id
                        all_simulation_data.append(report_df)
                        last_run_data = report_df
            except Exception as e: print(f"Error recogiendo datos (Sim {sim_id}): {e}")

        # --- Fin Bucle ---
        print(f"--- Simulaciones Terminadas ---")
        if all_simulation_data:
            self.aggregated_results = pd.concat(all_simulation_data, ignore_index=True)
            cols = ['simulation_id'] + [c for c in self.aggregated_results if c != 'simulation_id']
            self.aggregated_results = self.aggregated_results.reindex(columns=cols, fill_value=None)
            print(f"Info (Runner): Resultados agregados ({len(self.aggregated_results)} filas).")
            self.save_results()
            if self.config.print_last_run_summary and last_run_data is not None:
                self._show_run_summary(last_run_data)
        else: print("Advertencia (Runner): No se generaron datos agregados.")

    def get_results(self) -> Optional[pd.DataFrame]:
        return self.aggregated_results

    def save_results(self, output_filepath: Optional[str] = None):
        if self.aggregated_results is None or self.aggregated_results.empty:
            print("Advertencia (Runner): No hay resultados para guardar.")
            return
        if output_filepath is None: output_filepath = self.output_filepath
        try:
            output_dir = os.path.dirname(output_filepath); os.makedirs(output_dir, exist_ok=True)
            self.aggregated_results.to_csv(output_filepath, index=False)
            print(f"Info (Runner): Resultados guardados en '{output_filepath}'.")
        except Exception as e: print(f"Error (Runner): Falló al guardar resultados en '{output_filepath}': {e}"); traceback.print_exc()

    def _show_run_summary(self, report_df: pd.DataFrame):
        print("\n--- Resumen de Simulación (Última Ejecución Válida) ---")
        if report_df is None or report_df.empty: print("No hay datos."); return
        try:
            last_row = report_df.iloc[-1]
            time_col, compl_col, ev_col, ac_col, cpi_col = 'Time', 'Completion', 'EarnedValue', 'ActualCost', 'CPI'
            req_cols = [time_col, compl_col, ev_col, ac_col, cpi_col]
            if not all(c in last_row.index for c in req_cols): print(f"Error: Faltan columnas: {req_cols}. Encontradas: {last_row.index.tolist()}"); return
            print(f"Pasos: {last_row[time_col]}, Completado: {last_row[compl_col]:.2f}%, EV: {last_row[ev_col]:.2f}, AC: {last_row[ac_col]:.2f}", end="")
            cpi_val = last_row[cpi_col]
            if cpi_val == float('inf'): cpi_str = "Inf"
            elif pd.isna(cpi_val) or abs(cpi_val) < 1e-9: cpi_str = "0.00/NA"
            else: cpi_str = f"{cpi_val:.2f}"
            print(f", CPI: {cpi_str}")
        except Exception as e: print(f"Error generando resumen: {e}"); traceback.print_exc()
        print("----------------------------------------------------")