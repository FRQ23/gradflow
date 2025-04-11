# core/agents.py
import random
from typing import Optional, Tuple

# Importar clase base de Mesa y Agent
from mesa import Agent as MesaAgent

# Importar entidades del proyecto
try:
    from .entities import Task, Resource
    # Necesitamos una referencia al tipo Model para type hints, usar string
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from core.simulation.model import ProjectManagementModel # Ajusta ruta si es necesario
except ImportError:
    print("Advertencia: Usando importaciones directas en agents.py.")
    from entities import Task, Resource
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from core.simulation.model import ProjectManagementModel


class BaseProjectAgent(MesaAgent):
    """Clase base para agentes en la simulación, hereda de mesa.Agent."""
    def __init__(self, unique_id: int, model: 'ProjectManagementModel'):
        # Mesa requiere unique_id (int, usualmente) y model
        super().__init__(unique_id, model)
        self.current_task: Optional[Task] = None
        self.total_tasks_completed: int = 0

    def is_available(self) -> bool:
        """Verifica si el agente está libre."""
        return self.current_task is None

    def release(self):
        """Libera la tarea actual del agente."""
        # Considerar si la tarea debería volver a "to-do" aquí o en otro lugar
        self.current_task = None

    def reset(self):
        """Resetea el estado del agente para una nueva simulación."""
        self.current_task = None
        self.total_tasks_completed = 0

    def step(self):
        """Acción del agente en un paso de tiempo (a implementar por subclases)."""
        raise NotImplementedError("El método step() debe ser implementado por subclases de Agent.")

    def __repr__(self):
        # Una representación más informativa
        task_id = self.current_task.id if self.current_task else "None"
        return f"{type(self).__name__}(id={self.unique_id}, task={task_id})"

class TaskAgent(BaseProjectAgent):
    """Agente que representa un Recurso y puede ejecutar Tareas."""
    def __init__(self, unique_id: int, model: 'ProjectManagementModel', resource: Resource, efficiency: float = 1.0):
        """
        Inicializa un TaskAgent.

        Args:
            unique_id: ID único requerido por Mesa (podemos usar resource.id).
            model: La instancia del modelo Mesa al que pertenece el agente.
            resource: El objeto Resource asociado a este agente.
            efficiency: Factor de eficiencia base.
        """
        super().__init__(unique_id, model) # Llama al init de BaseProjectAgent/MesaAgent
        if not isinstance(resource, Resource):
            raise TypeError("TaskAgent requiere un objeto Resource.")
        self.resource = resource
        self.efficiency = efficiency
        # ID más descriptivo para logs, usando el recurso
        self.agent_log_id = f"Agent_{self.resource.id}_{self.resource.name}"

    def assign_task(self, task: Task):
        """Asigna una tarea si el agente está disponible."""
        if self.is_available() and isinstance(task, Task):
            self.current_task = task
            task.status = "in_progress"
            task.assigned_resource = self.resource
            # print(f"DEBUG: {self.agent_log_id} asignó Tarea {task.id} en t={self.model.schedule.steps}") # Log opcional
        # else: print(f"Adv (Agent): {self.agent_log_id} ocupado, no asignó Tarea {task.id}")

    def _execute_task_logic(self, error_margin: float) -> Tuple[bool, float]:
        """
        Lógica interna de ejecución de tarea (la misma que antes).
        Devuelve (completado?, costo_paso). Separada para claridad.
        """
        cost_incurred = 0.0
        task_completed = False
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

    # --- MÉTODO STEP (REQUERIDO POR MESA) ---
    def step(self):
        """Define la acción del TaskAgent en cada paso de tiempo."""
        cost_generated_this_step = 0.0 # Rastrear costo para posible recolección a nivel de agente

        # 1. Si estoy libre, intento buscar y asignarme una tarea
        if self.is_available():
            # Accedo al proyecto a través del modelo: self.model.project
            # Necesitaremos asegurarnos que ProjectManagementModel tenga self.project
            if hasattr(self.model, 'project'):
                available_task = self.model.project.get_next_available_task()
                if available_task:
                    self.assign_task(available_task)
                    # Nota: Si usamos SimultaneousActivation en Mesa, múltiples agentes podrían
                    # ver la misma tarea como disponible en el mismo sub-paso "antes" de
                    # que se actualice su estado/assigned_resource. Una cola centralizada
                    # de tareas en el modelo podría ser más robusta. Por ahora lo dejamos así.

        # 2. Si estoy asignado a una tarea, ejecuto trabajo
        if not self.is_available():
            # Llamar a la lógica de ejecución interna
            # Necesitamos el error_margin de los parámetros del modelo
            if hasattr(self.model, 'params'):
                 _, cost_generated_this_step = self._execute_task_logic(self.model.params.error_margin)
            else:
                 print(f"Error (Agent {self.unique_id}): Modelo no tiene 'params' para obtener error_margin.")

        # 3. (Opcional) Registrar métricas a nivel de agente si es necesario
        #    El DataCollector de Mesa puede hacer esto. Podríamos guardar cost_generated_this_step
        #    en un atributo si queremos recolectarlo directamente del agente.
        #    self.last_step_cost = cost_generated_this_step