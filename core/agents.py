# core/agents.py
import random
from typing import Optional, Tuple

# Importar clase base de Mesa y Agent
from mesa import Agent as MesaAgent

# Importar entidades del proyecto
try:
    from .entities import Task, Resource
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        # Usar ruta absoluta para evitar problemas con relativa aquí
        from core.simulation.model import ProjectManagementModel
except ImportError:
    print("Advertencia: Usando importaciones directas en agents.py.")
    from entities import Task, Resource
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from core.simulation.model import ProjectManagementModel


class BaseProjectAgent(MesaAgent):
    """Clase base para agentes, hereda de mesa.Agent (Patrón Mesa 3.0+)"""
    # --- INIT MODIFICADO (SIN unique_id) ---
    def __init__(self, model: 'ProjectManagementModel'):
        # No se pasa unique_id a super()
        super().__init__(model) # <-- CORREGIDO: Solo se pasa model
        self.current_task: Optional[Task] = None
        self.total_tasks_completed: int = 0
    # --- FIN INIT MODIFICADO ---

    # ... (is_available, release, reset, step - sin cambios estructurales) ...
    def is_available(self) -> bool: return self.current_task is None
    def release(self): self.current_task = None
    def reset(self): self.current_task = None; self.total_tasks_completed = 0
    def step(self): raise NotImplementedError("Implementar en subclase.")
    def __repr__(self):
        # self.unique_id es asignado por Mesa al añadir al schedule
        task_id = self.current_task.id if self.current_task else "None"
        # Usar self.unique_id asignado por Mesa
        uid = getattr(self, 'unique_id', 'N/A')
        return f"{type(self).__name__}(unique_id={uid}, task={task_id})"

class TaskAgent(BaseProjectAgent):
    """Agente que representa un Recurso y ejecuta Tareas (Patrón Mesa 3.0+)"""
    # --- INIT MODIFICADO (SIN unique_id) ---
    def __init__(self, model: 'ProjectManagementModel', resource: Resource, efficiency: float = 1.0):
        """
        Args:
            model: La instancia del modelo Mesa.
            resource: El objeto Resource asociado.
            efficiency: Factor de eficiencia base.
        """
        # No se pasa unique_id a super()
        super().__init__(model) # <-- CORREGIDO: Solo se pasa model
        if not isinstance(resource, Resource): raise TypeError("TaskAgent requiere Resource.")
        self.resource = resource
        self.efficiency = efficiency
        # Guardar el ID original del recurso si se necesita para logging/identificación
        self.resource_id_origin = resource.id
        self.agent_log_id = f"Agent_{self.resource.id}_{self.resource.name}" # Para logs
    # --- FIN INIT MODIFICADO ---

    # ... (assign_task - sin cambios) ...
    def assign_task(self, task: Task):
        if self.is_available() and isinstance(task, Task):
            self.current_task = task; task.status = "in_progress"; task.assigned_resource = self.resource

    # ... (_execute_task_logic - sin cambios) ...
    def _execute_task_logic(self, error_margin: float) -> Tuple[bool, float]:
        cost_incurred = 0.0; task_completed = False
        if not self.current_task: return task_completed, cost_incurred
        resource_cost_ph = getattr(self.resource, 'cost_per_hour', 0.0)
        if self.current_task.duration <= 0:
            if self.current_task.progress < 1.0:
                self.current_task.progress = 1.0; self.current_task.status = "done"
                self.total_tasks_completed += 1; task_completed = True
            ct = self.current_task; self.release();
            if ct: ct.assigned_resource = None
            return task_completed, 0.0
        cost_incurred = resource_cost_ph
        increment = (1.0 / max(1.0, self.current_task.duration)) * \
                    self.efficiency * (1 + random.uniform(-error_margin, error_margin))
        self.current_task.update_progress(increment)
        if hasattr(self.current_task, 'real_duration'): self.current_task.real_duration += 1
        if self.current_task.progress >= 1.0:
            self.total_tasks_completed += 1; task_completed = True
            ct = self.current_task; self.release()
            if ct: ct.assigned_resource = None
        return task_completed, cost_incurred

    # ... (step - sin cambios lógicos internos) ...
    def step(self):
        """Acción del TaskAgent en cada paso de tiempo."""
        if self.is_available():
            if hasattr(self.model, 'project'):
                available_task = self.model.project.get_next_available_task()
                if available_task:
                    self.assign_task(available_task)
        if not self.is_available():
            if hasattr(self.model, 'params'):
                 self._execute_task_logic(self.model.params.error_margin)