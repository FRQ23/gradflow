# core/project.py
# Ya NO necesita importar os ni aspose.tasks
from typing import Dict, List, Optional
from .entities import Task, Resource # Usar importación relativa

class Project:
    """Representa el proyecto, conteniendo tareas y recursos."""
    def __init__(self, project_name: Optional[str] = None):
        """Inicializa un proyecto vacío."""
        self.tasks: Dict[int, Task] = {} # UID -> Task
        self.resources: Dict[int, Resource] = {} # resource_id -> Resource
        # self.current_time ya no se usa aquí (manejado por Mesa)
        self.baseline_cost: float = 0.0
        self.project_name: Optional[str] = project_name
        # Calcular métricas base si se añaden tareas/recursos manualmente después
        self._calculate_baseline_metrics()

    # --- ELIMINADOS ---
    # load_from_mpp(self, file_path: str)
    # _process_mpp_task_recursive(self, mpp_task: tasks.Task, task_map_target: Dict[int, Task])
    # _process_mpp_dependencies(self, mpp: tasks.Project)
    # --- FIN ELIMINADOS ---

    def add_task(self, task: Task):
        """Añade o actualiza una tarea."""
        if not isinstance(task, Task): raise TypeError("Solo objetos Task.")
        self.tasks[task.id] = task # Usa UID como ID
        self._calculate_baseline_metrics() # Recalcular al añadir tarea

    def add_resource(self, resource: Resource):
        """Añade o actualiza un recurso."""
        if not isinstance(resource, Resource): raise TypeError("Solo objetos Resource.")
        self.resources[resource.id] = resource
        # No afecta baseline_cost basado en tareas

    def get_resource(self, resource_id: int) -> Optional[Resource]:
        return self.resources.get(resource_id)

    def get_all_resources(self) -> List[Resource]:
        return list(self.resources.values())

    def _calculate_baseline_metrics(self):
        """Recalcula costo base (suma de costos estimados de tareas)."""
        if self.tasks: self.baseline_cost = sum((t.estimated_cost or 0.0) for t in self.tasks.values())
        else: self.baseline_cost = 0.0

    def get_next_available_task(self) -> Optional[Task]:
        """Encuentra la siguiente tarea lista para empezar."""
        for task in self.tasks.values():
            if task.status == "to-do" and task.assigned_resource is None:
                if all(dep.status == "done" for dep in task.dependencies):
                    return task
        return None

    def reset_project_state(self):
        """Resetea estado de tareas para nueva simulación."""
        # Ya no resetea current_time
        for task in self.tasks.values():
            task.status = "to-do"; task.progress = 0.0
            task.real_duration = 0.0; task.assigned_resource = None

    def _clear_project_data(self):
        """Limpia tareas, recursos y estado (usado internamente por lectores)."""
        # Este método podría ser útil para los lectores antes de poblar
        self.tasks = {}; self.resources = {}
        self.baseline_cost = 0.0; self.project_name = None

    def __repr__(self):
        # Ya no incluye tiempo
        return (f"Project(name='{self.project_name}', tasks={len(self.tasks)}, "
                f"resources={len(self.resources)})")