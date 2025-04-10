# core/agents.py
import random
from typing import Optional, Tuple # Importar Tuple

# --- Importaciones ---
try:
    from .entities import Task, Resource
except ImportError:
    from entities import Task, Resource
# --- Fin Importaciones ---

class Agent:
    # ... (Sin cambios: __init__, is_available, release, reset) ...
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.current_task: Optional[Task] = None
        self.total_tasks_completed = 0

    def is_available(self) -> bool:
        return self.current_task is None

    def release(self):
        self.current_task = None

    def reset(self):
        self.current_task = None
        self.total_tasks_completed = 0


class TaskAgent(Agent):
    def __init__(self, resource: Resource, efficiency: float = 1.0):
        super().__init__(agent_id=f"Agent_{resource.id}_{resource.name}")
        self.resource = resource
        self.efficiency = efficiency

    def assign_task(self, task: Task):
        if self.is_available():
            self.current_task = task
            task.status = "in_progress"
            task.assigned_resource = self.resource
        else:
            print(f"Advertencia: Agente {self.agent_id} ya está ocupado, no se pudo asignar Tarea {task.id}")

    # --- MÉTODO EXECUTE_TASK MODIFICADO ---
    def execute_task(self, error_margin: float = 0.0) -> Tuple[bool, float]: # <-- Devuelve (completado, costo)
        """
        Ejecuta un paso de trabajo en la tarea actual.

        Returns:
            tuple[bool, float]: (True si la tarea se completó, Costo incurrido en este paso)
        """
        cost_incurred_this_step = 0.0
        task_completed_this_step = False

        if not self.current_task:
            # No hay tarea, no se trabaja, no hay costo
            return task_completed_this_step, cost_incurred_this_step # (False, 0.0)

        # Obtener costo del recurso asociado de forma segura
        resource_cost_per_hour = 0.0
        if hasattr(self, 'resource') and self.resource and hasattr(self.resource, 'cost_per_hour'):
            resource_cost_per_hour = self.resource.cost_per_hour

        # Manejar tareas con duración 0 (se completan pero no incurren en costo de ejecución)
        if self.current_task.duration <= 0:
             # print(f"Advertencia: Tarea {self.current_task.id} con duración {self.current_task.duration:.2f}. Completando instantáneamente.") # Comentado
             if self.current_task.progress < 1.0: # Solo marcar como completada una vez
                 self.current_task.progress = 1.0
                 self.current_task.status = "done"
                 self.total_tasks_completed += 1
                 task_completed_this_step = True # Se completó en este paso

             completed_task_ref = self.current_task
             self.release() # Liberar agente
             if completed_task_ref: completed_task_ref.assigned_resource = None # Desvincular recurso
             return task_completed_this_step, 0.0 # (True/False, 0.0) Costo cero

        # --- Si llegamos aquí, la tarea tiene duración > 0 y se trabaja ---
        cost_incurred_this_step = resource_cost_per_hour # Costo se incurre por trabajar en el paso

        # Calcular progreso
        base_increment_per_step = 1.0 / max(1.0, self.current_task.duration)
        efficiency_factor = self.efficiency * (1 + random.uniform(-error_margin, error_margin))
        progress_increment = base_increment_per_step * efficiency_factor
        self.current_task.update_progress(progress_increment)

        # Actualizar duración real
        if hasattr(self.current_task, 'real_duration'):
             self.current_task.real_duration += 1

        # Verificar si la tarea se completó justo ahora
        if self.current_task.progress >= 1.0:
            self.total_tasks_completed += 1
            task_completed_this_step = True # Se completó en este paso
            completed_task_ref = self.current_task
            self.release() # Liberar agente
            if completed_task_ref: completed_task_ref.assigned_resource = None # Desvincular recurso

        # Devolver si se completó Y el costo incurrido en este paso
        return task_completed_this_step, cost_incurred_this_step
    # --- FIN MÉTODO EXECUTE_TASK MODIFICADO ---