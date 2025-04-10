# core/simulation/runner.py
import os
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

# Importar componentes relativos necesarios
try:
    from ..project import Project
    from ..entities import Resource
    from .model import ProjectManagementModel
    from .parameters import SimulationParameters
    from ..tools import MetricsCollector
except (ImportError, ValueError):
    print("Advertencia: Usando importaciones directas en SimulationRunner.")
    from core.project import Project
    from core.entities import Resource
    from core.simulation.model import ProjectManagementModel
    from core.simulation.parameters import SimulationParameters
    from core.tools import MetricsCollector

@dataclass
class ExperimentConfig:
    """Define configuración para un experimento de simulación."""
    # Entradas
    mpp_file_name: str = "Software Development Plan.mpp"
    data_folder_relative_path: str = "data" # Relativo a la raíz del proyecto
    resources_definition: List[Dict[str, Any]] = field(default_factory=lambda: [
        {"id": 1, "name": "Developer_Jr", "cost_per_hour": 30.0},
        {"id": 2, "name": "Developer_Mid", "cost_per_hour": 45.0},
        {"id": 3, "name": "Developer_Sr", "cost_per_hour": 60.0},
    ])
    # Parámetros Simulación
    simulation_params: Dict[str, Any] = field(default_factory=lambda: {
        "error_margin": 0.15, "reassignment_frequency": 7, "max_steps": 500
    })
    # Configuración Ejecución y Salida
    num_simulations: int = 10
    output_folder_relative_path: str = "core/generated" # Relativo a la raíz
    output_filename_base: str = "simulation_results"
    add_timestamp_to_filename: bool = False
    print_last_run_summary: bool = True

class SimulationRunner:
    """Orquesta la ejecución de simulaciones basado en ExperimentConfig."""
    def __init__(self, config: ExperimentConfig):
        if not isinstance(config, ExperimentConfig): raise TypeError("config debe ser ExperimentConfig")
        self.config = config
        self.project_base: Optional[Project] = None
        self.simulation_params: Optional[SimulationParameters] = None
        self.aggregated_results: Optional[pd.DataFrame] = None
        self.collector = MetricsCollector()
        self._project_root = self._detect_project_root()
        self._setup_paths() # Preparar rutas al inicio

    def _detect_project_root(self) -> str:
        """Intenta detectar la carpeta raíz 'abp_simulator'."""
        try:
            # Asume que runner.py está en core/simulation/
            current_dir = os.path.dirname(__file__)
            root_path = os.path.normpath(os.path.join(current_dir, "..", ".."))
            # Si runner.py está en core/ directamente:
            # root_path = os.path.normpath(os.path.join(current_dir, ".."))
            if os.path.basename(root_path).lower() == 'abp_simulator': # Verificar nombre (opcional)
                 print(f"Info (Runner): Raíz del proyecto detectada en: {root_path}")
                 return root_path
        except NameError:
             pass # __file__ no definido
        # Fallback a directorio actual si falla la detección
        cwd = os.getcwd()
        print(f"Advertencia (Runner): No se pudo detectar raíz. Usando directorio actual: {cwd}")
        return cwd

    def _setup_paths(self):
        """Construye y valida rutas basado en config y raíz detectada."""
        self.input_mpp_path = os.path.join(self._project_root, self.config.data_folder_relative_path, self.config.mpp_file_name)
        self.input_mpp_path = os.path.normpath(self.input_mpp_path)
        if not os.path.exists(self.input_mpp_path):
            raise FileNotFoundError(f"Archivo MPP no encontrado: {self.input_mpp_path}")

        self.output_dir = os.path.join(self._project_root, self.config.output_folder_relative_path)
        self.output_dir = os.path.normpath(self.output_dir)
        output_filename = f"{self.config.output_filename_base}.csv"
        if self.config.add_timestamp_to_filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"{self.config.output_filename_base}_{timestamp}.csv"
        self.output_filepath = os.path.join(self.output_dir, output_filename)
        try:
            os.makedirs(self.output_dir, exist_ok=True)
        except OSError as e: raise OSError(f"No se pudo crear dir salida '{self.output_dir}': {e}")

    def _prepare_project_and_params(self):
        """Carga proyecto, añade recursos, prepara parámetros."""
        print(f"Info (Runner): Preparando proyecto desde '{self.input_mpp_path}'...")
        self.project_base = Project()
        self.project_base.load_from_mpp(self.input_mpp_path)
        if not self.project_base.tasks: raise ValueError("Proyecto MPP sin tareas de trabajo.")
        for res_data in self.config.resources_definition:
             try:
                 res = Resource(resource_id=res_data["id"], name=res_data["name"], cost_per_hour=float(res_data["cost_per_hour"]))
                 self.project_base.add_resource(res)
             except Exception as e: print(f"Adv (Runner): Ignorando recurso inválido {res_data}: {e}")
        if not self.project_base.resources: raise ValueError("No hay recursos válidos para simular.")
        print(f"Info (Runner): {len(self.project_base.resources)} recursos listos.")
        try:
            self.simulation_params = SimulationParameters(**self.config.simulation_params)
            print(f"Info (Runner): Parámetros listos: {self.simulation_params}")
        except TypeError as e: raise TypeError(f"Parámetros inválidos: {e}")

    def run(self):
        """Ejecuta el conjunto completo de simulaciones."""
        print(f"\n--- Iniciando {self.config.num_simulations} Simulaciones ---")
        all_simulation_data = []
        try:
            # Preparar proyecto y params una sola vez ANTES del bucle
            self._prepare_project_and_params()
        except Exception as e:
            print(f"Error Fatal en preparación: {e}")
            return

        for sim_id in range(1, self.config.num_simulations + 1):
            self.collector.reset()
            # print(f"--- Simulación {sim_id}/{self.config.num_simulations} ---") # Verboso
            try:
                # Pasar el proyecto base preparado (el modelo hará deepcopy)
                model = ProjectManagementModel(self.project_base, self.simulation_params)
            except Exception as e:
                print(f"Error Fatal: Creando modelo para simulación {sim_id}: {e}")
                return # Detener si falla creación

            while not model.is_simulation_complete(self.simulation_params.max_steps):
                model.step(self.collector)

            report_df = self.collector.generate_report()
            if not report_df.empty:
                report_df['simulation_id'] = sim_id
                all_simulation_data.append(report_df)

        print(f"--- Simulaciones Terminadas ---")
        if all_simulation_data:
            self.aggregated_results = pd.concat(all_simulation_data, ignore_index=True)
            cols = ['simulation_id'] + [col for col in self.aggregated_results.columns if col != 'simulation_id']
            self.aggregated_results = self.aggregated_results[[c for c in cols if c in self.aggregated_results.columns]]
            print(f"Info (Runner): Resultados agregados generados ({len(self.aggregated_results)} filas).")
            self.save_results() # Guardar automáticamente
            if self.config.print_last_run_summary: self.show_last_run_summary()
        else: print("Advertencia (Runner): No se generaron datos.")

    def get_results(self) -> Optional[pd.DataFrame]:
        return self.aggregated_results

    def save_results(self, output_filepath: Optional[str] = None):
        """Guarda resultados agregados en CSV."""
        if self.aggregated_results is None or self.aggregated_results.empty:
            print("Adv (Runner): No hay resultados agregados para guardar.")
            return
        if output_filepath is None: output_filepath = self.output_filepath
        try:
            output_dir = os.path.dirname(output_filepath)
            if output_dir: os.makedirs(output_dir, exist_ok=True)
            self.aggregated_results.to_csv(output_filepath, index=False)
            print(f"Info (Runner): Resultados agregados guardados en '{output_filepath}'.")
        except Exception as e: print(f"Error (Runner): Falló al guardar resultados en '{output_filepath}': {e}")

    def show_last_run_summary(self):
        """Muestra resumen de la última simulación."""
        print("\nResumen de la ÚLTIMA simulación ejecutada:")
        self.collector.present_results(filename=None, print_summary=True)