# core/readers/aspose_reader.py
import os
import aspose.tasks as tasks
from typing import Dict
# Importaciones absolutas desde core
from core.project import Project
from core.entities import Task # Asumimos que no carga Recursos desde MPP por ahora
from .base_reader import ProjectReader # Importar base relativa

class AsposeProjectReader(ProjectReader):
    """Lee archivos MPP usando Aspose.Tasks."""

    def load(self, file_path: str) -> Project:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"AsposeReader: Archivo no encontrado: {file_path}")

        print(f"Info (AsposeReader): Cargando desde '{file_path}'...")
        try:
            mpp = tasks.Project(file_path)
        except Exception as e:
            raise ValueError(f"AsposeReader: Fallo al cargar .mpp '{file_path}': {e}")

        # Crear una NUEVA instancia de Project para poblar
        project = Project(project_name=getattr(mpp.root_task, 'name', os.path.basename(file_path)))
        # Limpiar por si acaso (aunque es nueva instancia)
        project._clear_project_data()
        project.project_name = getattr(mpp.root_task, 'name', os.path.basename(file_path))


        task_map_during_load: Dict[int, Task] = {}
        # 1. Procesar Tareas
        try:
            self._process_mpp_task_recursive(mpp.root_task, task_map_during_load)
            # Añadir tareas al proyecto usando el método add_task (más limpio)
            for task_uid, task_obj in task_map_during_load.items():
                 project.add_task(task_obj) # add_task recalcula métricas base
            print(f"Info (AsposeReader): {len(project.tasks)} tareas de trabajo cargadas.")
        except Exception as e:
            raise ValueError(f"AsposeReader: Error procesando tareas en '{file_path}': {e}")

        # 2. Procesar Dependencias
        try:
            self._process_mpp_dependencies(mpp, project) # Pasar el proyecto poblado
        except Exception as e:
             raise ValueError(f"AsposeReader: Error procesando dependencias en '{file_path}': {e}")

        # 3. Recalcular métricas finales (aunque add_task lo hace incrementalmente)
        project._calculate_baseline_metrics()
        print(f"Info (AsposeReader): Carga completada. Costo base: {project.baseline_cost:.2f}")
        return project


    def _process_mpp_task_recursive(self, mpp_task: tasks.Task, task_map_target: Dict[int, Task]):
        """Auxiliar recursivo (idéntico al que estaba en Project)."""
        try:
            task_id = mpp_task.id
            if task_id != 0: # Omitir raíz
                is_summary = getattr(mpp_task, 'is_summary', False)
                task_uid = getattr(mpp_task, 'uid', None)
                if task_uid is not None and not is_summary:
                    task_name = getattr(mpp_task, 'name', f'Unnamed Task {task_uid}')
                    task_cost = getattr(mpp_task, 'cost', 0.0)
                    duration_obj = getattr(mpp_task, 'duration', None)
                    duration_hours = 0.0
                    if duration_obj:
                        try:
                            time_span = duration_obj.time_span
                            if time_span:
                                total_seconds = time_span.total_seconds()
                                if total_seconds >= 0: duration_hours = total_seconds / 3600
                        except Exception: pass
                    try:
                        # Usar la clase Task importada
                        new_task = Task(task_id=task_uid, name=task_name, duration=duration_hours,
                                        estimated_cost=float(task_cost) if task_cost is not None else 0.0)
                        task_map_target[task_uid] = new_task # Añadir al mapa temporal
                    except Exception as e: print(f"Adv (AsposeReader): Error creando Task UID={task_uid}: {e}")
        except Exception as e: print(f"Adv (AsposeReader): Error procesando tarea MPP (ID: {mpp_task.id if mpp_task else 'N/A'}): {e}")
        try:
            for child_task in mpp_task.children:
                 self._process_mpp_task_recursive(child_task, task_map_target)
        except Exception as e: print(f"Adv (AsposeReader): Error iterando hijas (ID: {mpp_task.id if mpp_task else 'N/A'}): {e}")


    def _process_mpp_dependencies(self, mpp: tasks.Project, project: Project):
        """Procesa dependencias y las añade al objeto Project dado."""
        added_deps = 0
        # project.tasks ahora contiene las tareas cargadas mapeadas por UID
        task_map = project.tasks
        for link in mpp.task_links:
            if link.link_type != tasks.TaskLinkType.FINISH_TO_START: continue
            pred_task_obj = getattr(link, 'pred_task', None); succ_task_obj = getattr(link, 'succ_task', None)
            if not pred_task_obj or not succ_task_obj: continue
            source_uid = getattr(pred_task_obj, 'uid', None); target_uid = getattr(succ_task_obj, 'uid', None)
            if source_uid is None or target_uid is None: continue
            # Usar el task_map del objeto project
            if target_uid in task_map and source_uid in task_map:
                target_task = task_map[target_uid]; source_task = task_map[source_uid]
                if not hasattr(target_task, 'dependencies') or target_task.dependencies is None: target_task.dependencies = []
                if source_task not in target_task.dependencies: target_task.dependencies.append(source_task); added_deps += 1
        print(f"Info (AsposeReader): {added_deps} dependencias Finish-to-Start añadidas.")