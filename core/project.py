# core/project.py
import os
import aspose.tasks as tasks
from typing import Dict, List, Optional

# Importar desde el mismo paquete 'core'
from .entities import Task, Resource

class Project:
    """
    Representa el proyecto, conteniendo tareas y recursos.
    Incluye funcionalidad para cargarse desde un archivo MPP.
    """
    def __init__(self, project_name: Optional[str] = None):
        """Inicializa un proyecto vacío."""
        self.tasks: Dict[int, Task] = {} # UID -> Task
        self.resources: Dict[int, Resource] = {} # resource_id -> Resource
        # self.current_time: int = 0 # <-- ELIMINADO (Usaremos schedule.steps de Mesa)
        self.baseline_cost: float = 0.0
        self.project_name: Optional[str] = project_name

    # ... (load_from_mpp, _process_mpp_task_recursive, _process_mpp_dependencies sin cambios) ...
    def load_from_mpp(self, file_path: str):
        if not os.path.exists(file_path): raise FileNotFoundError(f"No se pudo encontrar el archivo MPP: {file_path}")
        self._clear_project_data()
        print(f"Info (Project): Cargando desde '{file_path}'...")
        try:
            mpp = tasks.Project(file_path)
            self.project_name = getattr(mpp.root_task, 'name', os.path.basename(file_path))
        except Exception as e: raise ValueError(f"Fallo al cargar .mpp '{file_path}': {e}")
        task_map_during_load: Dict[int, Task] = {}
        try:
            self._process_mpp_task_recursive(mpp.root_task, task_map_during_load)
            self.tasks = task_map_during_load
            print(f"Info (Project): {len(self.tasks)} tareas de trabajo cargadas.")
        except Exception as e: print(f"Error Crítico procesando tareas MPP: {e}"); raise ValueError(f"Error procesando tareas en '{file_path}': {e}")
        try: self._process_mpp_dependencies(mpp)
        except Exception as e: print(f"Error procesando dependencias MPP: {e}"); raise ValueError(f"Error procesando dependencias en '{file_path}': {e}")
        self._calculate_baseline_metrics()
        # print(f"Info (Project): Carga completada. Costo base: {self.baseline_cost:.2f}") # Reducir verbosidad

    def _process_mpp_task_recursive(self, mpp_task: tasks.Task, task_map_target: Dict[int, Task]):
        try:
            task_id = mpp_task.id
            if task_id != 0:
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
                        new_task = Task(task_id=task_uid, name=task_name, duration=duration_hours,
                                        estimated_cost=float(task_cost) if task_cost is not None else 0.0)
                        task_map_target[task_uid] = new_task
                    except Exception as e: print(f"Adv (Project): Error creando Task UID={task_uid}: {e}")
        except Exception as e: print(f"Adv (Project): Error procesando tarea MPP (ID: {mpp_task.id if mpp_task else 'N/A'}): {e}")
        try:
            for child_task in mpp_task.children: self._process_mpp_task_recursive(child_task, task_map_target)
        except Exception as e: print(f"Adv (Project): Error iterando hijas (ID: {mpp_task.id if mpp_task else 'N/A'}): {e}")

    def _process_mpp_dependencies(self, mpp: tasks.Project):
        added_deps = 0
        for link in mpp.task_links:
            if link.link_type != tasks.TaskLinkType.FINISH_TO_START: continue
            pred_task_obj = getattr(link, 'pred_task', None); succ_task_obj = getattr(link, 'succ_task', None)
            if not pred_task_obj or not succ_task_obj: continue
            source_uid = getattr(pred_task_obj, 'uid', None); target_uid = getattr(succ_task_obj, 'uid', None)
            if source_uid is None or target_uid is None: continue
            if target_uid in self.tasks and source_uid in self.tasks:
                target_task = self.tasks[target_uid]; source_task = self.tasks[source_uid]
                if not hasattr(target_task, 'dependencies') or target_task.dependencies is None: target_task.dependencies = []
                if source_task not in target_task.dependencies: target_task.dependencies.append(source_task); added_deps += 1
        # print(f"Info (Project): {added_deps} dependencias Finish-to-Start añadidas.") # Reducir verbosidad

    # ... (add_resource, get_resource, get_all_resources sin cambios) ...
    def add_resource(self, resource: Resource):
        if not isinstance(resource, Resource): raise TypeError("Solo se pueden añadir objetos Resource.")
        self.resources[resource.id] = resource
    def get_resource(self, resource_id: int) -> Optional[Resource]: return self.resources.get(resource_id)
    def get_all_resources(self) -> List[Resource]: return list(self.resources.values())

    def _calculate_baseline_metrics(self):
        if self.tasks: self.baseline_cost = sum(task.estimated_cost for task in self.tasks.values())
        else: self.baseline_cost = 0.0

    def get_next_available_task(self) -> Optional[Task]:
        for task in self.tasks.values():
            if task.status == "to-do" and task.assigned_resource is None:
                if all(dep.status == "done" for dep in task.dependencies):
                    return task
        return None

    # def update_project_status(self): # <--- MÉTODO ELIMINADO
    #     self.current_time += 1

    def reset_project_state(self):
        """Resetea el estado para una nueva simulación."""
        # self.current_time = 0 # <-- ELIMINADO
        for task in self.tasks.values():
            task.status = "to-do"; task.progress = 0.0
            task.real_duration = 0.0; task.assigned_resource = None

    def _clear_project_data(self):
        """Limpia los datos internos del proyecto."""
        self.tasks = {}; self.resources = {}
        # self.current_time = 0 # <-- ELIMINADO
        self.baseline_cost = 0.0; self.project_name = None

    def __repr__(self):
        # Quitar current_time de la representación
        return (f"Project(name='{self.project_name}', tasks={len(self.tasks)}, "
                f"resources={len(self.resources)})")