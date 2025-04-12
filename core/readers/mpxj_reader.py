# core/readers/mpxj_reader.py
import os
from typing import Dict, Optional, Tuple
import jpype
import jpype.imports
from jpype.types import JString
import traceback

from core.project import Project
from core.entities import Task, Resource
from .base_reader import ProjectReader

_mpxj_reader_instance = None
_jvm_started = False

MPXJ_JAR_PATH = os.environ.get("MPXJ_JAR", r"C:\ruta\a\tu\libreria\mpxj-10.x.x.jar") # <-- ¡¡AJUSTA ESTA RUTA!!

def _start_jvm(jar_path: str):
    global _jvm_started
    if _jvm_started: return
    if not os.path.exists(jar_path):
        raise FileNotFoundError(f"MPXJ JAR no encontrado en: {jar_path}. Verifica la variable de entorno MPXJ_JAR o la ruta en mpxj_reader.py.")

    try:
        if not jpype.isJVMStarted():
            print(f"Info (MPXJ): Iniciando JVM con JAR: {jar_path}...")
            jpype.startJVM(classpath=[jar_path], convertStrings=False)
            _jvm_started = True
            print("Info (MPXJ): JVM iniciada.")
        else:
            _jvm_started = True
            print("Info (MPXJ): JVM ya estaba iniciada.")
    except Exception as e:
        print(f"Error Crítico (MPXJ): No se pudo iniciar la JVM: {e}")
        traceback.print_exc()
        _jvm_started = False
        raise RuntimeError(f"Fallo al iniciar JVM para MPXJ: {e}")

class MpxjProjectReader(ProjectReader):
    def __init__(self, mpxj_jar_path: str = MPXJ_JAR_PATH):
        self.jar_path = mpxj_jar_path
        _start_jvm(self.jar_path)
        try:
            # MODIFICADO: Importar más clases de MPXJ necesarias
            jpype.imports.load_java_packages()
            from net.sf.mpxj.reader import UniversalProjectReader
            from net.sf.mpxj import TaskField, ResourceField, Duration, ProjectFile, ResourceAssignment, Rate
            # NUEVO: Clases para recursos y asignaciones
            from net.sf.mpxj import Resource as MpxjResource # Renombrar para evitar conflicto
            from net.sf.mpxj.common import TimeUnit

            self.MPXJUniversalReader = UniversalProjectReader
            self.MPXJTaskField = TaskField
            self.MPXJResourceField = ResourceField
            self.MPXJDuration = Duration
            self.MPXJTimeUnit = TimeUnit # NUEVO
            self.MpxjResource = MpxjResource # NUEVO
            self.MPXJRate = Rate # NUEVO

            print("Info (MPXJReader): Clases Java MPXJ importadas.")
        except ImportError as e:
            print(f"Error Crítico (MPXJReader): No se pudieron importar clases MPXJ vía JPype: {e}")
            traceback.print_exc()
            raise RuntimeError("Fallo al importar clases MPXJ.")
        except Exception as e: # Captura errores más generales de JPype/JVM
            print(f"Error Crítico (MPXJReader): Error inesperado durante la importación de clases MPXJ: {e}")
            traceback.print_exc()
            raise RuntimeError(f"Fallo durante la inicialización de MPXJReader: {e}")

    def _get_cost_per_hour(self, mpxj_resource: 'MpxjResource') -> float:
        """Intenta obtener el costo por hora de un recurso MPXJ."""
        try:
            std_rate: Optional['Rate'] = mpxj_resource.getStandardRate()
            if std_rate is not None:
                # MPXJ devuelve el costo en la unidad de tiempo especificada (ej. /h, /d).
                # Necesitamos convertirlo a costo por HORA.
                rate_amount = float(std_rate.getAmount())
                rate_units = std_rate.getTimeUnits()

                if rate_units == self.MPXJTimeUnit.HOURS:
                    return rate_amount
                elif rate_units == self.MPXJTimeUnit.MINUTES:
                    return rate_amount * 60.0
                elif rate_units == self.MPXJTimeUnit.DAYS:
                    # Asumir 8 horas por día si no hay info específica
                    hours_per_day = 8.0 # Podría leerse de las opciones del calendario del proyecto
                    return rate_amount / hours_per_day
                elif rate_units == self.MPXJTimeUnit.WEEKS:
                    hours_per_week = 40.0 # Asumir 40 horas/semana
                    return rate_amount / hours_per_week
                # Añadir más conversiones si es necesario (meses, años)
                else:
                    print(f"Adv (MPXJReader): Unidad de tasa no manejada '{rate_units}' para Recurso ID {mpxj_resource.getID()}. Usando tasa como está.")
                    return rate_amount # Devolver sin convertir si la unidad es desconocida
            else:
                 # Intentar obtener del campo Cost si StandardRate no está
                 cost_val = mpxj_resource.getCost()
                 if cost_val is not None:
                     # Advertencia: Este campo 'Cost' puede no ser por hora.
                     print(f"Adv (MPXJReader): Recurso ID {mpxj_resource.getID()} no tiene StandardRate, usando campo Cost ({cost_val}). Asumiendo que es costo total o no por hora.")
                     # No podemos asumir que es por hora, devolver 0 o el valor con advertencia.
                     # return float(str(cost_val)) # Podría ser incorrecto
                     return 0.0 # Más seguro devolver 0 si no hay tasa por hora
        except Exception as e:
            print(f"Adv (MPXJReader): Error obteniendo costo/h para Recurso ID {mpxj_resource.getID()}: {e}")
        return 0.0 # Costo por defecto si no se puede obtener

    def load(self, file_path: str) -> Project:
        global _mpxj_reader_instance

        if not _jvm_started: raise RuntimeError("MPXJReader: JVM no está iniciada.")
        if not os.path.exists(file_path): raise FileNotFoundError(f"MPXJReader: Archivo no encontrado: {file_path}")

        print(f"Info (MPXJReader): Cargando desde '{file_path}'...")
        project = Project()
        project._clear_project_data()
        task_map: Dict[int, Task] = {}
        # NUEVO: Mapa para relacionar ID de recurso MPXJ con objeto Resource Python
        resource_map: Dict[int, Resource] = {}

        try:
            reader = self.MPXJUniversalReader()
            mpxj_project: Optional['ProjectFile'] = reader.read(JString(file_path))

            if mpxj_project is None: raise ValueError("MPXJ devolvió un proyecto nulo.")

            project.project_name = str(mpxj_project.getProjectHeader().getProjectTitle()) or os.path.basename(file_path)

            # --- NUEVO: Procesar Recursos Primero ---
            mpxj_resources = mpxj_project.getResources()
            if mpxj_resources:
                print(f"Info (MPXJReader): Procesando {mpxj_resources.size()} recursos MPXJ...")
                for mpxj_res in mpxj_resources:
                    try:
                        res_id = int(mpxj_res.getID()) # Usar getID() que suele ser más estable que UniqueID para recursos
                        res_unique_id = int(mpxj_res.getUniqueID()) # Guardar también el UniqueID por si acaso
                        res_name = str(mpxj_res.getName()) or f"Unnamed Resource {res_id}"

                        # Obtener costo por hora
                        cost_per_hour = self._get_cost_per_hour(mpxj_res)

                        # Crear objeto Resource Python
                        py_resource = Resource(resource_id=res_id, name=res_name, cost_per_hour=cost_per_hour)
                        project.add_resource(py_resource)
                        resource_map[res_unique_id] = py_resource # Mapear por UniqueID para las asignaciones
                        print(f"  -> Recurso Creado: {py_resource}")

                    except Exception as res_e:
                        print(f"Adv (MPXJReader): Error procesando recurso MPXJ: {res_e}")
                print(f"Info (MPXJReader): {len(project.resources)} recursos Python creados y añadidos al proyecto.")
            else:
                print("Adv (MPXJReader): No se encontraron recursos en el archivo MPXJ.")
                # Considerar si lanzar un error aquí si los recursos son obligatorios
                # raise ValueError("No se encontraron recursos en el archivo MPXJ, necesarios para la simulación.")

            # --- Procesar Tareas ---
            mpxj_tasks = mpxj_project.getTasks()
            if mpxj_tasks:
                print(f"Info (MPXJReader): Procesando {mpxj_tasks.size()} tareas MPXJ...")
                for mpxj_task in mpxj_tasks:
                    is_summary = bool(mpxj_task.getSummary())
                    # Usar UniqueID para tareas, es la clave consistente
                    task_unique_id = int(mpxj_task.getUniqueID())

                    # Ignorar tarea raíz (ID=0) y tareas resumen
                    if task_unique_id == 0 or is_summary: continue

                    try:
                        task_name = str(mpxj_task.getName()) or f"Unnamed Task {task_unique_id}"
                        mpxj_duration_obj = mpxj_task.getDuration()
                        duration_hours = 0.0
                        if mpxj_duration_obj:
                             try:
                                 # Obtener duración en minutos y convertir a horas
                                 duration_minutes = mpxj_duration_obj.getDuration() # Valor numérico
                                 duration_units = mpxj_duration_obj.getUnits() # TimeUnit (MINUTES, HOURS, etc.)
                                 if duration_minutes is not None:
                                     # Convertir a horas basado en la unidad
                                     if duration_units == self.MPXJTimeUnit.MINUTES:
                                         duration_hours = float(duration_minutes) / 60.0
                                     elif duration_units == self.MPXJTimeUnit.HOURS:
                                         duration_hours = float(duration_minutes)
                                     elif duration_units == self.MPXJTimeUnit.DAYS:
                                         duration_hours = float(duration_minutes) * 8.0 # Asumir 8h/día
                                     elif duration_units == self.MPXJTimeUnit.WEEKS:
                                          duration_hours = float(duration_minutes) * 40.0 # Asumir 40h/semana
                                     else:
                                         print(f"Adv (MPXJReader): Unidad de duración no manejada '{duration_units}' para Tarea ID {task_unique_id}. Usando valor como está.")
                                         duration_hours = float(duration_minutes) # Puede ser incorrecto
                             except Exception as dur_e:
                                 print(f"Adv (MPXJReader): Error convirtiendo duración para Tarea ID {task_unique_id}: {dur_e}")

                        task_cost = 0.0
                        try:
                            cost_obj = mpxj_task.getCost() # Costo estimado de la tarea (BCWS)
                            if cost_obj is not None:
                                task_cost = float(str(cost_obj)) # Convertir moneda a float
                        except Exception as cost_e:
                            print(f"Adv (MPXJReader): Error obteniendo costo para Tarea ID {task_unique_id}: {cost_e}")

                        # Crear objeto Task Python
                        py_task = Task(task_id=task_unique_id, name=task_name,
                                       duration=duration_hours, estimated_cost=task_cost)

                        # --- NUEVO: Procesar Asignaciones de Recursos para esta tarea ---
                        assignments = mpxj_task.getResourceAssignments()
                        assigned_resource_id: Optional[int] = None
                        if assignments and not assignments.isEmpty():
                            if assignments.size() > 1:
                                print(f"Adv (MPXJReader): Tarea ID {task_unique_id} ('{task_name}') tiene {assignments.size()} asignaciones. Usando la primera.")
                            # Tomar la primera asignación (simplificación)
                            first_assignment: Optional['ResourceAssignment'] = assignments.get(0)
                            if first_assignment:
                                assigned_mpxj_res_unique_id = int(first_assignment.getResourceUniqueID())
                                # Buscar el recurso Python correspondiente en nuestro mapa
                                assigned_py_resource = resource_map.get(assigned_mpxj_res_unique_id)
                                if assigned_py_resource:
                                    assigned_resource_id = assigned_py_resource.id # Guardar el ID del recurso Python
                                else:
                                    print(f"Adv (MPXJReader): Recurso asignado (UniqueID={assigned_mpxj_res_unique_id}) a Tarea ID {task_unique_id} no encontrado en los recursos procesados.")

                        # Establecer el recurso requerido en la tarea Python
                        py_task.required_resource_id = assigned_resource_id
                        # --- FIN Procesar Asignaciones ---

                        task_map[task_unique_id] = py_task
                        project.add_task(py_task)

                    except Exception as create_e:
                        print(f"Adv (MPXJReader): Error creando Task Python UID={task_unique_id}: {create_e}")
                        # traceback.print_exc() # Descomentar para depuración detallada

                print(f"Info (MPXJReader): {len(project.tasks)} tareas de trabajo creadas y añadidas al proyecto.")
            else:
                print("Adv (MPXJReader): No se encontraron tareas en el archivo MPXJ.")
                raise ValueError("No se encontraron tareas válidas en el archivo MPXJ.")


            # --- Procesar Dependencias ---
            added_deps = 0
            if mpxj_tasks:
                for mpxj_task in mpxj_tasks:
                    target_py_task = task_map.get(int(mpxj_task.getUniqueID()))
                    if target_py_task:
                        predecessors = mpxj_task.getPredecessors()
                        if predecessors and not predecessors.isEmpty():
                            for relation in predecessors:
                                # Solo considerar dependencias Fin-a-Comienzo (FS) por ahora
                                if str(relation.getType()) == "FS":
                                    source_mpxj_task = relation.getTargetTask()
                                    if source_mpxj_task:
                                        source_unique_id = int(source_mpxj_task.getUniqueID())
                                        source_py_task = task_map.get(source_unique_id)
                                        if source_py_task:
                                            # Añadir dependencia si no existe ya
                                            if source_py_task not in target_py_task.dependencies:
                                                target_py_task.dependencies.append(source_py_task)
                                                added_deps += 1
                                        # else: # Depuración: Tarea predecesora no encontrada en el mapa
                                        #     print(f"Adv (MPXJReader): Tarea predecesora (UID={source_unique_id}) para Tarea ID {target_py_task.id} no encontrada en task_map.")
                print(f"Info (MPXJReader): {added_deps} dependencias FS añadidas.")

            # Calcular métricas base (costo total estimado de tareas)
            project._calculate_baseline_metrics()
            print(f"Info (MPXJReader): Carga completada. Proyecto '{project.project_name}'.")
            print(f"  Tareas: {len(project.tasks)}, Recursos: {len(project.resources)}, Costo Base Planificado: {project.baseline_cost:.2f}")

        except jpype.JException as jex: # Capturar excepciones específicas de Java/JPype
             print(f"Error Crítico (MPXJReader - Java): Falló el procesamiento del archivo: {jex}")
             print("Stack trace de Java:")
             print(jex.stacktrace())
             raise ValueError(f"MPXJReader: Falló al procesar '{file_path}' debido a error Java: {jex.getMessage()}")
        except Exception as e:
            print(f"Error Crítico (MPXJReader - Python): Falló el procesamiento del archivo: {e}")
            traceback.print_exc()
            raise ValueError(f"MPXJReader: Falló al leer o procesar '{file_path}': {e}")

        # Validar que el proyecto tenga recursos si son necesarios
        if not project.resources:
             print("Error Crítico (MPXJReader): No se cargaron recursos del archivo MPXJ. La simulación requiere recursos.")
             raise ValueError("Proyecto cargado no contiene recursos.")

        return project