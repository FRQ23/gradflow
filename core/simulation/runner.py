# core/simulation/runner.py
import os
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

# Importar componentes necesarios de la biblioteca 'core'
# (Las rutas relativas asumen que runner.py está en core/simulation/)
try:
    from ..project import Project
    from ..entities import Resource # Necesitamos Resource para instanciar desde config
    from .model import ProjectManagementModel # El modelo Mesa
    from .parameters import SimulationParameters
    # Ya NO importamos MetricsCollector
except (ImportError, ValueError):
    # Fallback si las importaciones relativas fallan
    print("Advertencia: Usando importaciones directas en SimulationRunner (Mesa).")
    from core.project import Project
    from core.entities import Resource
    from core.simulation.model import ProjectManagementModel # Modelo Mesa
    from core.simulation.parameters import SimulationParameters


@dataclass
class ExperimentConfig:
    """Define configuración para un experimento de simulación."""
    # Entradas
    mpp_file_name: str = "Software Development Plan.mpp"
    data_folder_relative_path: str = "data" # Relativo a la raíz del proyecto

    # Definición de Recursos a Usar en la Simulación
    # *** CORREGIDO: Usar 'resource_id' como clave ***
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
        # Ya no necesitamos un collector externo, el modelo Mesa tiene el suyo
        self._project_root = self._detect_project_root()
        # Preparar rutas una vez al inicio
        self._setup_paths()

    def _detect_project_root(self) -> str:
        """Intenta detectar la carpeta raíz del proyecto."""
        try:
            # Asume __file__ está en core/simulation/runner.py -> ../.. llega a la raíz
            current_dir = os.path.dirname(__file__)
            root_path = os.path.normpath(os.path.join(current_dir, "..", ".."))
            # Verificación simple buscando la carpeta 'core'
            if os.path.isdir(os.path.join(root_path, 'core')):
                 # print(f"Info (Runner): Raíz del proyecto detectada en: {root_path}") # Opcional
                 return root_path
        except NameError: pass # __file__ no definido
        # Fallback
        cwd = os.getcwd()
        print(f"Advertencia (Runner): No se pudo auto-detectar raíz del proyecto. Usando directorio actual: {cwd}")
        return cwd

    def _setup_paths(self):
        """Construye y valida rutas basado en config y raíz detectada."""
        # Ruta MPP
        self.input_mpp_path = os.path.join(self._project_root, self.config.data_folder_relative_path, self.config.mpp_file_name)
        self.input_mpp_path = os.path.normpath(self.input_mpp_path)
        if not os.path.exists(self.input_mpp_path):
            raise FileNotFoundError(f"Archivo MPP no encontrado: {self.input_mpp_path}")

        # Ruta Salida CSV
        self.output_dir = os.path.join(self._project_root, self.config.output_folder_relative_path)
        self.output_dir = os.path.normpath(self.output_dir)
        output_filename = f"{self.config.output_filename_base}.csv"
        if self.config.add_timestamp_to_filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"{self.config.output_filename_base}_{timestamp}.csv"
        self.output_filepath = os.path.join(self.output_dir, output_filename)
        try:
            os.makedirs(self.output_dir, exist_ok=True) # Crear directorio si no existe
        except OSError as e:
            raise OSError(f"No se pudo crear directorio de salida '{self.output_dir}': {e}")

    def _prepare_project_and_params(self):
        """Carga el proyecto MPP, añade recursos y prepara parámetros."""
        print(f"Info (Runner): Preparando proyecto desde '{self.input_mpp_path}'...")
        self.project_base = Project() # Crear proyecto vacío
        self.project_base.load_from_mpp(self.input_mpp_path) # Cargar datos
        if not self.project_base.tasks:
             raise ValueError("El proyecto MPP cargado no contiene tareas de trabajo.")

        # Añadir recursos desde la configuración
        num_resources_added = 0
        for res_data in self.config.resources_definition:
             try:
                 # Usar desempaquetado (**), esperando 'resource_id' en res_data
                 res = Resource(**res_data)
                 self.project_base.add_resource(res)
                 num_resources_added += 1
             except (TypeError, KeyError, ValueError) as e:
                 # Imprimir advertencia si un recurso de la config es inválido
                 print(f"Advertencia (Runner): Ignorando definición de recurso inválida {res_data}: {e}")

        if num_resources_added == 0: # Verificar si se añadió al menos uno
             raise ValueError("No se definieron o añadieron recursos válidos desde la configuración.")
        print(f"Info (Runner): {num_resources_added} recursos añadidos al proyecto base.")

        # Preparar parámetros de simulación
        try:
            # Usar desempaquetado (**) para pasar el diccionario a SimulationParameters
            self.simulation_params = SimulationParameters(**self.config.simulation_params)
            print(f"Info (Runner): Parámetros de simulación listos: {self.simulation_params}")
        except TypeError as e:
             # Error si las claves en config.simulation_params no coinciden con SimulationParameters
             raise TypeError(f"Parámetros de simulación inválidos en config: {e}")

    def run(self):
        """Ejecuta el conjunto completo de simulaciones usando el modelo Mesa."""
        print(f"\n--- Iniciando {self.config.num_simulations} Simulaciones (Usando Mesa) ---")
        all_simulation_data = []
        last_run_data: Optional[pd.DataFrame] = None # Para guardar datos de la última ejecución

        try:
            # Preparar proyecto y params una sola vez ANTES del bucle de simulaciones
            self._prepare_project_and_params()
            print(f"Info (Runner): Preparación completada. Ejecutando simulaciones...")
        except Exception as e:
            print(f"Error Fatal en la fase de preparación: {e}")
            return # Salir si falla la preparación

        for sim_id in range(1, self.config.num_simulations + 1):
            # Imprimir progreso cada N simulaciones podría ser útil si son muchas
            # if sim_id % 10 == 0: print(f"--- Iniciando Simulación {sim_id}/{self.config.num_simulations} ---")
            try:
                # Crear el modelo Mesa para esta simulación (usa deepcopy interno del proyecto base)
                model = ProjectManagementModel(self.project_base, self.simulation_params)
            except Exception as e:
                print(f"Error Fatal: Creando modelo Mesa para simulación {sim_id}: {e}")
                return # Detener si falla creación

            # Ejecutar el modelo Mesa por N pasos
            max_steps = self.simulation_params.max_steps
            try:
                for _ in range(max_steps):
                    if hasattr(model, 'running') and not model.running: # Comprobar si el modelo Mesa se detuvo
                        break
                    model.step() # Ejecuta un paso de Mesa
                final_step_count = model.schedule.steps
            except Exception as e:
                 print(f"Error durante la ejecución de pasos (Sim {sim_id}): {e}")
                 continue # Saltar a la siguiente simulación si una falla

            # Recoger datos del DataCollector del modelo
            try:
                if hasattr(model, 'datacollector') and model.datacollector:
                    report_df = model.datacollector.get_model_vars_dataframe()
                    if not report_df.empty:
                        report_df['simulation_id'] = sim_id
                        all_simulation_data.append(report_df)
                        last_run_data = report_df # Guardar para el resumen
                else:
                     print(f"Error: Modelo Sim {sim_id} no tiene 'datacollector' válido.")
            except Exception as e:
                print(f"Error recogiendo datos del DataCollector para Sim {sim_id}: {e}")

        # --- Fin Bucle de Simulaciones ---
        print(f"--- {self.config.num_simulations} Simulaciones Terminadas ---")

        if all_simulation_data:
            self.aggregated_results = pd.concat(all_simulation_data, ignore_index=True)
            # Reordenar columnas de forma segura
            cols_ordered = ['simulation_id'] + [col for col in self.aggregated_results.columns if col != 'simulation_id']
            self.aggregated_results = self.aggregated_results.reindex(columns=cols_ordered, fill_value=None)
            print(f"Info (Runner): Resultados agregados generados ({len(self.aggregated_results)} filas).")
            # Guardar automáticamente los resultados agregados
            self.save_results()
            # Mostrar resumen de la última simulación si está configurado
            if self.config.print_last_run_summary and last_run_data is not None:
                self._show_run_summary(last_run_data) # Usar método auxiliar privado
        else:
            print("Advertencia (Runner): No se generaron datos agregados en ninguna simulación.")


    def get_results(self) -> Optional[pd.DataFrame]:
        """Devuelve el DataFrame con los resultados agregados."""
        if self.aggregated_results is None:
             print("Advertencia (Runner): No hay resultados agregados. Ejecuta run() primero.")
        return self.aggregated_results


    def save_results(self, output_filepath: Optional[str] = None):
        """Guarda los resultados agregados en un archivo CSV."""
        if self.aggregated_results is None or self.aggregated_results.empty:
            print("Advertencia (Runner): No hay resultados agregados para guardar.")
            return
        # Usar ruta preparada si no se especifica otra
        if output_filepath is None:
            output_filepath = self.output_filepath # Usar la ruta preparada en _setup_paths
        # Asegurar que el directorio exista por si se llama save_results antes que run()
        try:
            output_dir = os.path.dirname(output_filepath)
            if output_dir: os.makedirs(output_dir, exist_ok=True) # Crear si no existe
            self.aggregated_results.to_csv(output_filepath, index=False)
            print(f"Info (Runner): Resultados agregados guardados en '{output_filepath}'.")
        except Exception as e:
            print(f"Error (Runner): Falló al guardar resultados en '{output_filepath}': {e}")


    def _show_run_summary(self, report_df: pd.DataFrame):
        """Método auxiliar para mostrar el resumen de un DataFrame de resultados de simulación."""
        # La lógica es la misma que la del present_results del antiguo MetricsCollector
        print("\n--- Resumen de Simulación (Última Ejecución Válida) ---")
        if report_df is None or report_df.empty:
            print("No hay datos disponibles para mostrar resumen.")
            return
        try:
            last_row = report_df.iloc[-1]
            # Nombres de columna deben coincidir con los 'model_reporters' definidos en ProjectManagementModel
            time_col = 'Time'; compl_col = 'Completion'; ev_col = 'EarnedValue'
            ac_col = 'ActualCost'; cpi_col = 'CPI'
            req_cols = [time_col, compl_col, ev_col, ac_col, cpi_col]
            if not all(col in last_row.index for col in req_cols):
                 print(f"Error: Faltan columnas en el reporte: {req_cols}")
                 print(f"Columnas encontradas: {last_row.index.tolist()}")
                 return

            print(f"Pasos de Tiempo Totales: {last_row[time_col]}")
            print(f"Completitud Final: {last_row[compl_col]:.2f}%")
            print(f"Valor Ganado Final (EV): {last_row[ev_col]:.2f}")
            print(f"Costo Actual Final (AC): {last_row[ac_col]:.2f}")
            cpi_val = last_row[cpi_col]
            if cpi_val == float('inf'): cpi_str = "Inf"
            elif pd.isna(cpi_val) or abs(cpi_val) < 1e-9 : cpi_str = "0.00 / N/A"
            else: cpi_str = f"{cpi_val:.2f}"
            print(f"Índice de Desempeño del Costo (CPI): {cpi_str}")
        except (IndexError, KeyError, TypeError) as e:
             print(f"Error generando resumen de la última ejecución: {e}")
        print("----------------------------------------------------")