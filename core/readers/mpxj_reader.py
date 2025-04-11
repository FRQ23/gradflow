# core/readers/mpxj_reader.py
import os
from typing import Dict, Optional
import jpype
import jpype.imports
from jpype.types import JString

from core.project import Project
from core.entities import Task, Resource
from .base_reader import ProjectReader

_mpxj_reader_instance = None
_jvm_started = False

# --- CONFIGURACIÓN MPXJ ---
MPXJ_JAR_PATH = os.environ.get("MPXJ_JAR", r"C:\Users\PC TENSE\PycharmProjects\abp_simulator_mesa\libs\mpxj-test.jar")
# --- FIN CONFIGURACIÓN ---

def _start_jvm(jar_path: str):
    global _jvm_started
    if _jvm_started:
        return
    if not os.path.exists(jar_path):
        raise FileNotFoundError(f"MPXJ JAR no encontrado en: {jar_path}")

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
        _jvm_started = False
        raise RuntimeError(f"Fallo al iniciar JVM para MPXJ: {e}")

class MpxjProjectReader(ProjectReader):
    def __init__(self, mpxj_jar_path: str = MPXJ_JAR_PATH):
        self.jar_path = mpxj_jar_path
        _start_jvm(self.jar_path)
        try:
            jpype.imports.load_java_packages()
            from net.sf.mpxj.reader import UniversalProjectReader
            from net.sf.mpxj import TaskField, ResourceField, Duration
            self.MPXJUniversalReader = UniversalProjectReader
            self.MPXJTaskField = TaskField
            self.MPXJResourceField = ResourceField
            self.MPXJDuration = Duration
            print("Info (MPXJReader): Clases Java MPXJ importadas.")
        except ImportError as e:
            print(f"Error Crítico (MPXJReader): No se pudieron importar clases MPXJ vía JPype: {e}")
            raise RuntimeError("Fallo al importar clases MPXJ.")

    def load(self, file_path: str) -> Project:
        global _mpxj_reader_instance

        if not _jvm_started:
            raise RuntimeError("MPXJReader: JVM no está iniciada.")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"MPXJReader: Archivo no encontrado: {file_path}")

        print(f"Info (MPXJReader): Cargando desde '{file_path}'...")
        project = Project()
        project._clear_project_data()
        task_map: Dict[int, Task] = {}

        try:
            reader = self.MPXJUniversalReader()
            mpxj_project = reader.read(JString(file_path))

            if mpxj_project is None:
                raise ValueError("MPXJ devolvió un proyecto nulo.")

            project.project_name = str(mpxj_project.getProjectHeader().getProjectTitle()) or os.path.basename(file_path)

            mpxj_tasks = mpxj_project.getTasks()
            if mpxj_tasks:
                print(f"Info (MPXJReader): Procesando {mpxj_tasks.size()} tareas MPXJ...")
                for mpxj_task in mpxj_tasks:
                    is_summary = bool(mpxj_task.getSummary())
                    task_unique_id = int(mpxj_task.getUniqueID())

                    if task_unique_id != 0 and not is_summary:
                        task_name = str(mpxj_task.getName()) or f"Unnamed Task {task_unique_id}"
                        mpxj_duration_obj = mpxj_task.getDuration()
                        duration_hours = 0.0
                        if mpxj_duration_obj:
                            try:
                                duration_minutes = mpxj_duration_obj.getDuration()
                                if duration_minutes: duration_hours = float(duration_minutes) / 60.0
                            except Exception as dur_e:
                                print(f"Adv (MPXJReader): Error convirtiendo duración para Tarea ID {task_unique_id}: {dur_e}")

                        task_cost = 0.0
                        try:
                            cost_obj = mpxj_task.getCost()
                            if cost_obj is not None:
                                task_cost = float(cost_obj.toString())
                        except Exception as cost_e:
                            print(f"Adv (MPXJReader): Error obteniendo costo para Tarea ID {task_unique_id}: {cost_e}")

                        try:
                            py_task = Task(task_id=task_unique_id, name=task_name,
                                           duration=duration_hours, estimated_cost=task_cost)
                            task_map[task_unique_id] = py_task
                            project.add_task(py_task)
                        except Exception as create_e:
                            print(f"Adv (MPXJReader): Error creando Task Python UID={task_unique_id}: {create_e}")

                print(f"Info (MPXJReader): {len(project.tasks)} tareas de trabajo creadas.")

            added_deps = 0
            if mpxj_tasks:
                for mpxj_task in mpxj_tasks:
                    target_py_task = task_map.get(int(mpxj_task.getUniqueID()))
                    if target_py_task:
                        predecessors = mpxj_task.getPredecessors()
                        if predecessors:
                            for relation in predecessors:
                                if str(relation.getType()) == "FS":
                                    source_mpxj_task = relation.getTargetTask()
                                    if source_mpxj_task:
                                        source_unique_id = int(source_mpxj_task.getUniqueID())
                                        source_py_task = task_map.get(source_unique_id)
                                        if source_py_task:
                                            if not hasattr(target_py_task, 'dependencies') or target_py_task.dependencies is None:
                                                target_py_task.dependencies = []
                                            if source_py_task not in target_py_task.dependencies:
                                                target_py_task.dependencies.append(source_py_task)
                                                added_deps += 1
                print(f"Info (MPXJReader): {added_deps} dependencias FS añadidas.")

            project._calculate_baseline_metrics()
            print(f"Info (MPXJReader): Carga completada. Costo base: {project.baseline_cost:.2f}")

        except Exception as e:
            print(f"Error Crítico (MPXJReader): Falló el procesamiento del archivo: {e}")
            import traceback
            traceback.print_exc()
            raise ValueError(f"MPXJReader: Falló al leer o procesar '{file_path}': {e}")

        return project
