# core/readers/aspose_reader.py
import os
import traceback
from typing import Dict, Optional

# --- Importaciones de Aspose ---
try:
    import aspose.tasks as tasks
    print("Info (AsposeReader): Librería 'aspose-tasks' importada.")
except ImportError:
    # ... (manejo de error de importación) ...
    raise ImportError("Librería 'aspose-tasks' no encontrada.")

# --- Importaciones del Proyecto Core ---
from core.project import Project
from core.entities import Task, Resource
from .base_reader import ProjectReader

class AsposeProjectReader(ProjectReader):
    """
    Lector Aspose.Tasks.
    Versión que interpreta los tipos de recurso de forma estándar:
    SOLO procesa recursos de TIPO 0 (Work) para crear agentes.
    """

    def __init__(self):
        # ... (licencia si aplica) ...
        pass

    def _get_aspose_cost_per_hour(self, aspose_resource: tasks.Resource) -> float:
        """Intenta obtener el costo por HORA de un recurso Aspose."""
        try:
            # Acceso directo a atributos
            std_rate_decimal = aspose_resource.standard_rate
            std_rate_format_enum = aspose_resource.standard_rate_format
            if std_rate_decimal is None or std_rate_format_enum is None: return 0.0
            rate_amount = float(std_rate_decimal)

            # Conversión basada en formato de tasa
            if std_rate_format_enum == tasks.RateFormatType.MINUTE: return rate_amount * 60.0
            if std_rate_format_enum == tasks.RateFormatType.HOUR: return rate_amount
            if std_rate_format_enum == tasks.RateFormatType.DAY: return rate_amount / 8.0
            if std_rate_format_enum == tasks.RateFormatType.WEEK: return rate_amount / 40.0
            if std_rate_format_enum == tasks.RateFormatType.MONTH_BY_DAY or \
               std_rate_format_enum == tasks.RateFormatType.MONTH_BY_HOUR: return rate_amount / 160.0
            if std_rate_format_enum == tasks.RateFormatType.YEAR: return rate_amount / 1920.0
            # Ignorar costo si es Material o tipo no manejado
            if std_rate_format_enum == tasks.RateFormatType.MATERIAL: return 0.0
            return 0.0 # Default
        except AttributeError: pass # Ignorar si faltan atributos de costo/tasa
        except Exception as e: print(f"Adv (AsposeReader Costo): Excepción obteniendo costo/h para Recurso ID {getattr(aspose_resource, 'id', 'N/A')}: {e}")
        return 0.0

    def _get_aspose_duration_hours(self, aspose_task: tasks.Task) -> float:
        """Convierte un objeto Duration de Aspose a horas."""
        try:
            # Acceso directo a atributo 'duration'
            aspose_duration = aspose_task.duration
            if aspose_duration is None: return 0.0
            time_span = aspose_duration.time_span
            if time_span: return time_span.total_hours
            else: # Plan B
                 duration_value = float(aspose_duration.get_value())
                 duration_unit = aspose_duration.time_unit
                 if duration_unit == tasks.TimeUnitType.MINUTE: return duration_value / 60.0
                 if duration_unit == tasks.TimeUnitType.HOUR: return duration_value
                 if duration_unit == tasks.TimeUnitType.DAY: return duration_value * 8.0
                 if duration_unit == tasks.TimeUnitType.WEEK: return duration_value * 40.0
                 return duration_value # Devolver como está si no se maneja la unidad
        except AttributeError: pass # Ignorar si falta atributo duration
        except Exception as e: print(f"Adv (AsposeReader Duración): Excepción convirtiendo duración a horas para Tarea UID {getattr(aspose_task, 'unique_id', 'N/A')}: {e}")
        return 0.0

    def load(self, file_path: str) -> Project:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"AsposeReader: Archivo no encontrado: {file_path}")

        print(f"Info (AsposeReader): Cargando proyecto desde '{file_path}'...")
        project = Project()
        project._clear_project_data()
        resource_map: Dict[int, Resource] = {}
        task_map: Dict[int, Task] = {}

        try:
            prj = tasks.Project(file_path)
            # Obtener nombre del proyecto
            try: project.project_name = prj.title or os.path.basename(file_path)
            except AttributeError:
                 try: project.project_name = prj.subject or os.path.basename(file_path)
                 except AttributeError: project.project_name = os.path.basename(file_path)

            # --- 1. Procesar Recursos ---
            print(f"Info (AsposeReader): Procesando {len(prj.resources)} recursos encontrados...")
            resources_processed = 0
            resource_list = list(prj.resources)
            print(f"Info (AsposeReader): Iniciando iteración sobre {len(resource_list)} recursos...")

            for index, res in enumerate(resource_list):
                res_name = None
                res_id_val = None
                res_type = None
                try:
                    # --- CHEQUEOS INICIALES BÁSICOS ---
                    if res is None or res.is_null: continue
                    res_id_val = res.id
                    if res_id_val == 0: continue # Saltar recurso nulo interno
                    res_name = res.name
                    if res_name is None: continue # Saltar recursos sin nombre
                    # --- FIN CHEQUEOS BÁSICOS ---

                    # --- INICIO CHEQUEO DE TIPO ---
                    # Obtener el tipo reportado por Aspose
                    res_type = res.type # tasks.ResourceType enum (WORK=0, MATERIAL=1, COST=2)

                    # --- OPCIÓN 1: Lógica Correcta (ACTIVA AHORA) ---
                    # Acepta SÓLO recursos que Aspose reporta como TIPO 0 (Work).
                    if res_type != tasks.ResourceType.WORK: # WORK es 0
                        # print(f"  Debug: Recurso ID={res_id_val} es tipo {res_type}. Saltando (Se necesita WORK).")
                        continue # Saltar si no es tipo Trabajo

                    # --- OPCIÓN 2: Workaround para Aceptar Tipo 1 (Comentada) ---
                    # if res_type != tasks.ResourceType.MATERIAL: # MATERIAL es 1
                    #     continue # Saltar si NO es Tipo 1
                    # --- FIN CHEQUEO DE TIPO ---


                    # Si pasa los chequeos (ID>0, Nombre no Nulo, y TIPO=0 según Aspose), procesar
                    res_id_int = int(res_id_val)
                    cost_per_hour = self._get_aspose_cost_per_hour(res)

                    # Crear el recurso Python
                    py_resource = Resource(resource_id=res_id_int, name=res_name, cost_per_hour=cost_per_hour)
                    project.add_resource(py_resource)
                    resource_map[res_id_int] = py_resource

                    resources_processed += 1
                    # Imprimir confirmación
                    print(f"  --> Recurso WORK Aceptado: ID={res_id_int}, Nombre='{res_name}', Costo/h={cost_per_hour:.2f} (Total: {resources_processed})")

                except AttributeError as attr_e:
                     print(f"  Adv (AsposeReader): Falta atributo durante chequeo/procesamiento del recurso índice {index}: {attr_e}.")
                     # traceback.print_exc()
                except Exception as res_proc_e:
                     id_str = f"ID={res_id_val}" if res_id_val is not None else "ID?"
                     name_str = f"Nombre='{res_name}'" if res_name is not None else "Nombre?"
                     print(f"  Adv (AsposeReader): Error procesando datos del recurso {index} ({id_str}, {name_str}): {res_proc_e}")
                     # traceback.print_exc()


            print(f"\nInfo (AsposeReader): Fin del bucle de recursos. resources_processed = {resources_processed}")
            # Modificar mensaje de error/éxito según la lógica activa (Opción 1)
            if resources_processed == 0:
                 print("Error Crítico (AsposeReader): No se cargaron recursos válidos de tipo WORK (Tipo 0).")
                 raise ValueError("Proyecto cargado no contiene recursos de trabajo válidos para la simulación.")
            else:
                 print(f"Info (AsposeReader): {resources_processed} recursos de tipo WORK procesados.")


            # --- 2. Procesar Tareas y Asignaciones ---
            # (Sin cambios aquí)
            print(f"Info (AsposeReader): Procesando tareas...")
            tasks_processed = 0
            task_map: Dict[int, Task] = {}

            for tsk in prj.root_task.select_all_children():
                 if tsk is None or tsk.is_null: continue
                 if tsk.is_summary: continue
                 task_unique_id = tsk.unique_id
                 if task_unique_id == 0: continue
                 try:
                     task_uid = int(task_unique_id)
                     task_name = tsk.name or f"Unnamed Task UID {task_uid}"
                     duration_hours = self._get_aspose_duration_hours(tsk)
                     task_cost = float(tsk.cost or 0.0)
                     py_task = Task(task_id=task_uid, name=task_name, duration=duration_hours, estimated_cost=task_cost)
                     assigned_resource_id: Optional[int] = None
                     assignments = list(tsk.assignments)
                     if assignments:
                         for assignment in assignments:
                             if assignment and assignment.resource:
                                 assigned_resource_obj = assignment.resource
                                 if assigned_resource_obj and not assigned_resource_obj.is_null:
                                     assigned_aspose_res_id = int(assigned_resource_obj.id)
                                     if assigned_aspose_res_id != 0:
                                         # Buscar en nuestro resource_map (que ahora solo tiene recursos WORK)
                                         assigned_py_resource = resource_map.get(assigned_aspose_res_id)
                                         if assigned_py_resource:
                                             assigned_resource_id = assigned_py_resource.id
                                             break
                     py_task.required_resource_id = assigned_resource_id
                     project.add_task(py_task)
                     task_map[task_uid] = py_task
                     tasks_processed += 1
                 except AttributeError as attr_e:
                      print(f"Adv (AsposeReader): Falta atributo en tarea UID={task_unique_id}: {attr_e}.")
                 except Exception as task_e:
                     error_task_uid_str = f"UID={task_unique_id}" if tsk else "N/A"
                     print(f"Adv (AsposeReader): Error procesando tarea Aspose ({error_task_uid_str}): {task_e}")
                     traceback.print_exc()

            if tasks_processed == 0:
                 print("Error Crítico (AsposeReader): No se cargaron tareas válidas.")
                 raise ValueError("Proyecto cargado no contiene tareas válidas.")
            else:
                 print(f"Info (AsposeReader): {tasks_processed} tareas de trabajo procesadas.")


            # --- 3. Procesar Dependencias ---
            # (Sin cambios aquí)
            print(f"Info (AsposeReader): Procesando {len(prj.task_links)} dependencias...")
            links_processed = 0
            if prj.task_links:
                for link in prj.task_links:
                     if link is None: continue
                     try:
                         link_type = link.link_type
                         pred = link.predecessor
                         succ = link.successor
                         if link_type == tasks.TaskLinkType.FINISH_TO_START:
                             if pred and succ and not pred.is_null and not succ.is_null:
                                 pred_task_uid = int(pred.unique_id)
                                 succ_task_uid = int(succ.unique_id)
                                 if pred_task_uid != 0 and succ_task_uid != 0:
                                     pred_py_task = task_map.get(pred_task_uid)
                                     succ_py_task = task_map.get(succ_task_uid)
                                     if pred_py_task and succ_py_task:
                                         if pred_py_task not in succ_py_task.dependencies:
                                             succ_py_task.dependencies.append(pred_py_task)
                                             links_processed += 1
                     except AttributeError as attr_e:
                          print(f"Adv (AsposeReader): Falta atributo en link dependencia: {attr_e}.")
                     except Exception as link_e:
                          pred_id = pred.id if pred else 'N/A'
                          succ_id = succ.id if succ else 'N/A'
                          print(f"Adv (AsposeReader): Error procesando dependencia ({pred_id} -> {succ_id}): {link_e}")
            print(f"Info (AsposeReader): {links_processed} dependencias FS procesadas.")


            # --- 4. Finalizar y Calcular Baseline ---
            project._calculate_baseline_metrics()
            print(f"Info (AsposeReader): Carga completada. Proyecto '{project.project_name}'.")
            print(f"  Tareas: {len(project.tasks)}, Recursos: {len(project.resources)}, Costo Base Planificado: {project.baseline_cost:.2f}")

        except Exception as e:
            print(f"Error Crítico (AsposeReader): Falló la carga o procesamiento del archivo '{file_path}': {e}")
            traceback.print_exc()
            raise ValueError(f"AsposeReader: Falló al leer o procesar '{file_path}': {e}")

        return project