# core/simulation/runner.py
import os
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import traceback
import jpype # Para MPXJ

# --- Importaciones (sin cambios) ---
try:
    from core.project import Project
    from core.entities import Resource, Task
    from core.simulation.model import ProjectManagementModel
    from core.simulation.parameters import SimulationParameters
    from core.readers.base_reader import ProjectReader
    from core.readers.aspose_reader import AsposeProjectReader
    from core.readers.mpxj_reader import MpxjProjectReader
    from core.readers.xml_reader import XmlProjectReader
except ImportError as e:
     print(f"Error Fatal: No se pudieron importar componentes desde 'core' o 'core/readers': {e}")
     print("Asegúrate de que 'core' esté en PYTHONPATH y existan los archivos __init__.py y los lectores.")
     raise e
# --- Fin Importaciones ---


@dataclass
class ExperimentConfig:
    # --- (Clase ExperimentConfig sin cambios respecto a la versión anterior) ---
    """Define configuración para un experimento de simulación."""
    # Entradas
    mpp_file_name: str = "project.xml" # Nombre del archivo (XML por defecto)
    data_folder_relative_path: str = "data"
    reader_type: str = "xml" # Opciones: "xml", "mpxj", "aspose"
    # Para actualizar costos
    resources_definition: List[Dict[str, Any]] = field(default_factory=list)
    # Parámetros Simulación
    simulation_params: Dict[str, Any] = field(default_factory=lambda: {
        "error_margin": 0.15,
        "reassignment_frequency": 0,
        "max_steps": 1500
    })
    # Configuración Ejecución y Salida
    num_simulations: int = 5
    output_folder_relative_path: str = "core/generated"
    output_filename_base: str = "simulation_results_xml" # Nombre base por defecto
    add_timestamp_to_filename: bool = True
    print_last_run_summary: bool = True
    # --- Opciones de Visualización ---
    show_loaded_tasks: bool = False       # Opción para mostrar tareas cargadas
    show_loaded_resources: bool = False   # Opción para mostrar recursos/agentes cargados
    display_limit: int = 20               # Límite de items a mostrar para tareas/recursos


class SimulationRunner:
    # --- (__init__, _detect_project_root, _setup_paths sin cambios) ---
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
             traceback.print_exc()
             raise

    def _detect_project_root(self) -> str:
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            root_path = os.path.normpath(os.path.join(current_dir, "..", ".."))
            if os.path.isdir(os.path.join(root_path, 'core')) and \
               (os.path.isdir(os.path.join(root_path, self.config.data_folder_relative_path)) or \
                os.path.exists(os.path.join(root_path, 'requirements.txt'))):
                 print(f"Info (Runner): Raíz del proyecto detectada en: {root_path}")
                 return root_path
        except Exception as e:
            print(f"Advertencia (Runner): Excepción detectando raíz: {e}")
            pass
        cwd = os.getcwd()
        print(f"Advertencia (Runner): No se pudo auto-detectar raíz robustamente. Usando directorio actual: {cwd}")
        return cwd

    def _setup_paths(self):
        self.input_project_file_path = os.path.join(self._project_root, self.config.data_folder_relative_path, self.config.mpp_file_name)
        self.input_project_file_path = os.path.normpath(self.input_project_file_path)
        print(f"Info (Runner): Verificando archivo de entrada en: {self.input_project_file_path}")
        if not os.path.exists(self.input_project_file_path):
            raise FileNotFoundError(f"Archivo de entrada no encontrado: {self.input_project_file_path}")
        self.output_dir = os.path.join(self._project_root, self.config.output_folder_relative_path)
        self.output_dir = os.path.normpath(self.output_dir)
        output_filename = f"{self.config.output_filename_base}.csv"
        if self.config.add_timestamp_to_filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"{self.config.output_filename_base}_{timestamp}.csv"
        self.output_filepath = os.path.join(self.output_dir, output_filename)
        print(f"Info (Runner): Directorio de salida será: {self.output_dir}")
        try:
            os.makedirs(self.output_dir, exist_ok=True)
        except OSError as e:
            raise OSError(f"No se pudo crear directorio de salida '{self.output_dir}': {e}")


    def _prepare_project_and_params(self):
        # --- (_prepare_project_and_params sin cambios respecto a la versión anterior) ---
        # (Este método ya contiene la lógica de selección de lector, carga,
        #  visualización opcional de tareas/recursos y actualización de costos)
        print(f"Info (Runner): Preparando proyecto desde '{self.input_project_file_path}'...")
        reader: Optional[ProjectReader] = None
        reader_choice = self.config.reader_type.lower()
        print(f"Info (Runner): Usando lector tipo '{reader_choice}'...")
        if reader_choice == "mpxj":
            try:
                 jpype.startJVM(jpype.getDefaultJVMPath(), "-ea", classpath=["libs/*"])
                 reader = MpxjProjectReader()
                 print("Info (Runner): Instancia de MpxjProjectReader creada.")
            except (FileNotFoundError, RuntimeError, ImportError, jpype.JException) as mpxj_e:
                 print(f"Error Fatal: No se pudo inicializar MPXJReader: {mpxj_e}")
                 raise mpxj_e
        elif reader_choice == "aspose":
            try:
                from core.readers.aspose_reader import AsposeProjectReader
                reader = AsposeProjectReader()
                print("Info (Runner): Instancia de AsposeProjectReader creada.")
            except ImportError:
                 print("Error Fatal: Librería 'aspose-tasks' no instalada o AsposeProjectReader no encontrado.")
                 raise ImportError("Se requiere 'aspose-tasks' para usar el lector Aspose.")
            except Exception as aspose_e:
                 print(f"Error Fatal: No se pudo inicializar AsposeProjectReader: {aspose_e}")
                 raise aspose_e
        elif reader_choice == "xml":
             try:
                 reader = XmlProjectReader()
                 print("Info (Runner): Instancia de XmlProjectReader creada.")
             except Exception as xml_e:
                  print(f"Error Fatal: No se pudo inicializar XmlProjectReader: {xml_e}")
                  raise xml_e
        else:
            raise ValueError(f"Tipo de lector desconocido: '{self.config.reader_type}'. Opciones: 'mpxj', 'aspose', 'xml'.")

        try:
            self.project_base = reader.load(self.input_project_file_path)
        except (FileNotFoundError, ValueError, RuntimeError) as load_e:
             print(f"Error Fatal: El lector '{reader_choice}' falló al cargar '{self.input_project_file_path}': {load_e}")
             traceback.print_exc()
             raise load_e

        if not self.project_base: raise ValueError("El lector no devolvió un objeto Project.")
        if not self.project_base.tasks: raise ValueError("El proyecto cargado no contiene tareas válidas (no resumen).")

        print(f"Info (Runner): Proyecto '{self.project_base.project_name}' cargado ({len(self.project_base.tasks)} tareas, {len(self.project_base.resources)} recursos).")
        print(f"Info (Runner): Costo base planificado: {self.project_base.baseline_cost:.2f}")

        display_limit = self.config.display_limit
        if self.config.show_loaded_tasks:
            print(f"\n--- Lista de Tareas Cargadas (Trabajo - max {display_limit}) ---")
            if self.project_base.tasks:
                for i, task in enumerate(self.project_base.get_all_tasks()):
                    if i >= display_limit: print(f"  ... y {len(self.project_base.tasks) - display_limit} tareas más."); break
                    res_id_str = f"Req. Res: {task.required_resource_id}" if task.required_resource_id is not None else "Req. Res: N/A"
                    dep_str = f"Deps: {len(task.dependencies)}"
                    print(f"  - ID: {task.id:<5} | Nombre: {task.name[:35]:<35} | Dur: {task.duration:<6.1f}h | Costo: {task.estimated_cost:<7.2f} | {res_id_str:<15} | {dep_str}")
            else: print("  (No hay tareas de trabajo cargadas)")
            print("-" * 86) # Ajustar ancho línea

        if self.config.show_loaded_resources:
            print(f"\n--- Muestra de Recursos/Agentes Cargados (Trabajo - max {display_limit}) ---")
            if self.project_base.resources:
                for i, resource in enumerate(self.project_base.get_all_resources()):
                    if i >= display_limit: print(f"  ... y {len(self.project_base.resources) - display_limit} recursos más."); break
                    print(f"  - ID: {resource.id:<5} | Nombre: {resource.name[:40]:<40} | Costo/h: {resource.cost_per_hour:<7.2f}")
            else: print("  (No hay recursos de trabajo cargados)")
            print("-" * 86) # Ajustar ancho línea

        num_resources_updated = 0
        if self.config.resources_definition:
            print(f"Info (Runner): Intentando actualizar costos para {len(self.config.resources_definition)} recursos definidos en ExperimentConfig...")
            loaded_resources_map: Dict[int, Resource] = {res.id: res for res in self.project_base.get_all_resources()}
            for res_data_config in self.config.resources_definition:
                try:
                    res_id_config = res_data_config.get('resource_id')
                    cost_config = res_data_config.get('cost_per_hour')
                    if res_id_config is None or cost_config is None: continue
                    target_resource = loaded_resources_map.get(res_id_config)
                    if target_resource:
                        old_cost = target_resource.cost_per_hour
                        new_cost = float(cost_config)
                        target_resource.cost_per_hour = max(0.0, new_cost)
                        num_resources_updated += 1
                except (TypeError, ValueError, KeyError) as e: print(f"Adv: Error procesando def. recurso de config {res_data_config}: {e}")
            print(f"Info (Runner): {num_resources_updated} costos de recursos actualizados desde la configuración.")
        else: print("Info (Runner): No se actualizaron costos desde config.")

        try:
            self.simulation_params = SimulationParameters(**self.config.simulation_params)
            print(f"Info (Runner): Parámetros de simulación listos: {self.simulation_params}")
        except TypeError as e: raise TypeError(f"Parámetros inválidos en config ('simulation_params'): {e}")


    # --- MÉTODO run() MODIFICADO ---
    def run(self):
        """Ejecuta el ciclo completo de preparación y simulación, manejando errores internamente."""
        main_start_time = datetime.now()
        print(f"\n--- Iniciando {self.config.num_simulations} Simulaciones ({self.config.reader_type.upper()}) ---")

        all_simulation_data = []
        last_run_data: Optional[pd.DataFrame] = None
        successful_sims = 0
        preparation_ok = False

        try: # --- Bloque TRY principal que envuelve toda la ejecución ---
            # Fase 1: Preparación
            try:
                self._prepare_project_and_params()
                preparation_ok = True # Marcar que la preparación fue exitosa
                print(f"Info (Runner): Preparación completada. Ejecutando simulaciones...")
            except Exception as prep_e:
                # Captura cualquier error durante la preparación
                print(f"\n!!! Error Fatal durante la Preparación del Proyecto !!!")
                print(f"  Tipo de Error: {type(prep_e).__name__}")
                print(f"  Mensaje      : {prep_e}")
                print("  -------------------- Traceback --------------------")
                traceback.print_exc() # Muestra detalles para depuración
                print("  ---------------------------------------------------")
                print("  La ejecución no puede continuar.")
                # No continuar si la preparación falla
                # Salimos del bloque try principal, y el finally se ejecutará

            # Fase 2: Ejecución de Simulaciones (Solo si la preparación fue OK)
            if preparation_ok:
                for sim_id in range(1, self.config.num_simulations + 1):
                    sim_start_time = datetime.now()
                    print(f"--- Simulación {sim_id}/{self.config.num_simulations} ---")
                    model: Optional[ProjectManagementModel] = None
                    sim_success = False # Flag para esta simulación específica
                    try:
                        # Crear el modelo Mesa
                        if not self.project_base or not self.simulation_params:
                            print(f"  Error Interno (Sim {sim_id}): project_base o simulation_params no están listos.")
                            continue # Saltar al siguiente sim_id

                        model = ProjectManagementModel(self.project_base, self.simulation_params)

                        # Ejecutar los pasos del modelo
                        max_steps = self.simulation_params.max_steps
                        for i in range(max_steps):
                            if not model.running: break
                            model.step()
                        final_step_count = model.schedule.steps

                        if model.running and final_step_count == max_steps:
                            print(f"  Advertencia (Sim {sim_id}): Simulación alcanzó max_steps ({max_steps}).")
                        else:
                            print(f"  Info (Sim {sim_id}): Simulación completada en {final_step_count} pasos.")

                        sim_success = True # Marcamos como exitosa si llega aquí sin excepción

                    except Exception as sim_exec_e:
                        # Captura errores durante la creación o ejecución de UNA simulación
                        print(f"  Error durante Simulación {sim_id}: {sim_exec_e}")
                        traceback.print_exc() # Mostrar detalles
                        # Continuar con la siguiente simulación si es posible

                    # Recolectar datos SI la simulación tuvo éxito (o al menos no crasheó)
                    if model: # Si el modelo llegó a crearse
                         try:
                             if hasattr(model, 'datacollector') and model.datacollector:
                                 report_df = model.datacollector.get_model_vars_dataframe()
                                 if not report_df.empty:
                                     report_df['simulation_id'] = sim_id
                                     all_simulation_data.append(report_df)
                                     last_run_data = report_df # Actualizar para el resumen
                                     if sim_success: successful_sims += 1 # Contar solo si hubo datos Y no falló
                         except Exception as dc_e:
                             print(f"  Error recogiendo datos (Sim {sim_id}): {dc_e}")
                             # No fallar todo, solo loguear

                    sim_end_time = datetime.now()
                    print(f"--- Simulación {sim_id} Terminada (Duración: {sim_end_time - sim_start_time}) ---")


            # Fase 3: Agregación y Guardado de Resultados (Fuera del loop, si hubo datos)
            if all_simulation_data:
                try:
                    self.aggregated_results = pd.concat(all_simulation_data, ignore_index=True)
                    cols_order = ['simulation_id', 'Time', 'Completion', 'EarnedValue', 'ActualCost', 'CPI', 'SPI', 'ActiveAgents']
                    existing_cols = [c for c in cols_order if c in self.aggregated_results.columns]
                    other_cols = [c for c in self.aggregated_results.columns if c not in existing_cols]
                    self.aggregated_results = self.aggregated_results[existing_cols + other_cols]
                    print(f"Info (Runner): Resultados agregados generados ({len(self.aggregated_results)} filas).")
                    self.save_results() # Guarda en archivo CSV
                    if self.config.print_last_run_summary and last_run_data is not None:
                        self._show_run_summary(last_run_data)
                except Exception as agg_e:
                    print(f"Error procesando/guardando resultados agregados: {agg_e}")
                    traceback.print_exc() # Mostrar error
            elif successful_sims > 0:
                print("Advertencia (Runner): Simulaciones terminaron pero no se generaron datos para agregar.")
            elif preparation_ok: # Si preparación OK pero 0 sims exitosas con datos
                 print("Error (Runner): Ninguna simulación pudo completarse exitosamente o generar datos.")
            # Si preparation_ok es False, el error ya se reportó en Fase 1

        except Exception as e: # --- Captura errores MUY inesperados fuera de la preparación/loop ---
            print(f"\n !!! Error Inesperado MUY GRAVE durante la ejecución del Runner !!!")
            print(f"  Tipo de Error: {type(e).__name__}")
            print(f"  Mensaje      : {e}")
            print("  Por favor, revise el traceback para depurar el código del Runner:")
            print("  -------------------- Traceback --------------------")
            traceback.print_exc()
            print("  ---------------------------------------------------")

        finally: # --- Bloque FINALLY para asegurar limpieza y reporte final ---
            # Finalizar JVM si se usó MPXJ y está iniciada
            if self.config.reader_type.lower() == "mpxj" and jpype.isJVMStarted():
                 try:
                     jpype.shutdownJVM()
                     print("Info (Runner): JVM de JPype finalizada.")
                 except Exception as jvm_shutdown_e:
                      print(f"Adv (Runner): Error al finalizar JVM: {jvm_shutdown_e}")

            # Reporte final de tiempo y éxito
            main_end_time = datetime.now()
            total_duration = main_end_time - main_start_time
            print(f"\n--- {successful_sims}/{self.config.num_simulations} Simulaciones Reportadas como Exitosas (con datos) ---")
            print(f"Tiempo Total de Ejecución del Runner: {total_duration}")
            print("runner.run() finalizado.")


    # --- (get_results, save_results, _show_run_summary sin cambios) ---
    def get_results(self) -> Optional[pd.DataFrame]:
        return self.aggregated_results

    def save_results(self, output_filepath: Optional[str] = None):
        if self.aggregated_results is None or self.aggregated_results.empty:
            print("Adv (Runner): No hay resultados agregados para guardar.")
            return
        if output_filepath is None: output_filepath = self.output_filepath
        try:
            output_dir = os.path.dirname(output_filepath); os.makedirs(output_dir, exist_ok=True)
            self.aggregated_results.to_csv(output_filepath, index=False, float_format='%.2f')
            print(f"Info (Runner): Resultados agregados guardados en '{output_filepath}'.")
        except Exception as e: print(f"Error (Runner): Falló al guardar resultados en '{output_filepath}': {e}")

    def _show_run_summary(self, report_df: pd.DataFrame):
        print("\n--- Resumen Sim (Última Ejecución Válida) ---")
        if report_df is None or report_df.empty: print("No hay datos disponibles para mostrar resumen."); return
        try:
            last_state = report_df.iloc[-1]
            time_col, comp_col, ev_col, ac_col, cpi_col, spi_col = 'Time', 'Completion', 'EarnedValue', 'ActualCost', 'CPI', 'SPI'
            required_cols = [time_col, comp_col, ev_col, ac_col, cpi_col]
            if not all(col in last_state.index for col in required_cols):
                missing = [col for col in required_cols if col not in last_state.index]; print(f"Error Resumen: Faltan columnas: {missing}"); return
            steps = last_state[time_col]; completion = last_state[comp_col]; ev = last_state[ev_col]; ac = last_state[ac_col]; cpi = last_state[cpi_col]; spi = last_state.get(spi_col, None)
            if pd.isna(cpi): cpi_str = "N/A"
            elif cpi == float('inf') or (abs(ac) < 1e-9 and ev > 0): cpi_str = "Inf (AC~0)"
            elif abs(cpi) < 1e-9: cpi_str = "0.00 (EV=0)"
            else: cpi_str = f"{cpi:.2f}"
            spi_str = "N/A"
            if spi is not None:
                 if pd.isna(spi): spi_str = "N/A"
                 elif spi == float('inf'): spi_str = "Inf"
                 else: spi_str = f"{spi:.2f}"
            print(f"  Pasos Finales                : {steps}")
            print(f"  Completitud Final            : {completion:.1f}%")
            print(f"  Valor Ganado (EV)            : {ev:.2f}")
            print(f"  Costo Real (AC)              : {ac:.2f}")
            print(f"  Índice Desempeño Costo (CPI) : {cpi_str}")
            if spi is not None: print(f"  Índice Desempeño Plazo (SPI) : {spi_str}")
            if cpi_str not in ["N/A", "Inf (AC~0)", "0.00 (EV=0)"]:
                numeric_cpi = float(cpi)
                if numeric_cpi < 1.0: print(f"    -> Desviación de Costo: {ac - ev:.2f} (Sobre costo)")
                elif numeric_cpi > 1.0: print(f"    -> Ahorro de Costo    : {ev - ac:.2f} (Bajo costo)")
                else: print("    -> En presupuesto.")
        except Exception as e: print(f"Error generando resumen: {e}"); traceback.print_exc()
        print("-" * 86) # Ajustar ancho línea