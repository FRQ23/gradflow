# core/project.py
# Ya NO necesita importar os ni aspose.tasks
from typing import Dict, List, Optional
# Usar importación relativa dentro del mismo paquete 'core'
from .entities import Task, Resource

class Project:
    """Representa el proyecto, conteniendo tareas y recursos."""
    def __init__(self, project_name: Optional[str] = None):
        """Inicializa un proyecto vacío."""
        self.tasks: Dict[int, Task] = {} # Diccionario: Task Unique ID -> Objeto Task
        self.resources: Dict[int, Resource] = {} # Diccionario: Resource ID -> Objeto Resource
        # self.current_time ya no se usa aquí (manejado por Mesa)
        self.baseline_cost: float = 0.0 # Costo base planificado (suma de costos estimados de tareas)
        self.project_name: Optional[str] = project_name
        # Calcular métricas base si se añaden tareas/recursos manualmente después
        self._calculate_baseline_metrics()

    # --- MÉTODOS ELIMINADOS (si existían versiones anteriores que usaban librerías específicas aquí) ---
    # load_from_mpp(self, file_path: str) # La carga ahora la hacen los Readers
    # _process_mpp_task_recursive(...)
    # _process_mpp_dependencies(...)
    # --- FIN ELIMINADOS ---

    def add_task(self, task: Task):
        """Añade o actualiza una tarea en el diccionario de tareas."""
        if not isinstance(task, Task):
            raise TypeError("El objeto añadido debe ser una instancia de Task.")
        # Usar el ID de la tarea (que debería ser el Unique ID del MPP/MPXJ/Aspose) como clave
        self.tasks[task.id] = task
        # Recalcular métricas base cada vez que se añade una tarea
        self._calculate_baseline_metrics()

    def add_resource(self, resource: Resource):
        """Añade o actualiza un recurso en el diccionario de recursos."""
        if not isinstance(resource, Resource):
            raise TypeError("El objeto añadido debe ser una instancia de Resource.")
        # Usar el ID del recurso como clave
        self.resources[resource.id] = resource
        # Añadir un recurso no afecta directamente al baseline_cost basado en tareas

    def get_resource(self, resource_id: int) -> Optional[Resource]:
        """Obtiene un recurso por su ID."""
        return self.resources.get(resource_id)

    def get_all_resources(self) -> List[Resource]:
        """Devuelve una lista de todos los objetos Resource del proyecto."""
        return list(self.resources.values())

    def get_all_tasks(self) -> List[Task]:
         """Devuelve una lista de todos los objetos Task del proyecto."""
         return list(self.tasks.values())

    def _calculate_baseline_metrics(self):
        """
        Recalcula el costo base del proyecto.
        Actualmente, se basa en la suma de los costos estimados de todas las tareas.
        """
        if self.tasks:
            self.baseline_cost = sum((t.estimated_cost or 0.0) for t in self.tasks.values())
        else:
            self.baseline_cost = 0.0

    # NOTA: Este método ya no es utilizado directamente por el TaskAgent modificado,
    # ya que ahora cada agente busca tareas que requieran su recurso específico.
    # Se mantiene aquí por si es útil para otros propósitos o análisis.
    def get_next_available_task(self) -> Optional[Task]:
        """
        [NO USADO POR AGENTES ACTUALES] Encuentra la siguiente tarea genérica
        que está lista para empezar (to-do, sin asignar, dependencias cumplidas).
        """
        for task in self.tasks.values():
            if task.status == "to-do" and task.assigned_resource is None:
                # Verificar que todas las dependencias estén completadas
                if all(dep.status == "done" for dep in task.dependencies):
                    return task
        return None # No hay tareas disponibles que cumplan los criterios

    def reset_project_state(self):
        """
        Resetea el estado dinámico de todas las tareas para una nueva simulación.
        Útil para ejecutar múltiples simulaciones sobre el mismo plan base.
        """
        # Ya no resetea current_time (lo maneja Mesa)
        for task in self.tasks.values():
            task.status = "to-do"
            task.progress = 0.0
            task.real_duration = 0.0
            task.assigned_resource = None # Desasignar recursos al inicio de la simulación

    def _clear_project_data(self):
        """
        Limpia completamente los datos del proyecto (tareas, recursos, métricas).
        Usado internamente por los lectores antes de cargar un nuevo archivo.
        """
        self.tasks = {}
        self.resources = {}
        self.baseline_cost = 0.0
        self.project_name = None

    def __repr__(self):
        """Representación textual del objeto Project."""
        # Ya no incluye tiempo
        return (f"Project(name='{self.project_name}', tasks={len(self.tasks)}, "
                f"resources={len(self.resources)}, baseline_cost={self.baseline_cost:.2f})")