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
        from core.simulation.model import ProjectManagementModel # Usar ruta absoluta
except ImportError:
    print("Advertencia: Usando importaciones directas en agents.py (puede fallar si no se ejecuta desde la raíz).")
    from entities import Task, Resource
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from model import ProjectManagementModel # Asume que model.py está en el mismo nivel


class BaseProjectAgent(MesaAgent):
    """Clase base para agentes, hereda de mesa.Agent."""
    def __init__(self, model: 'ProjectManagementModel'):
        super().__init__(model) # Mesa 3.0+ asigna unique_id automáticamente
        self.current_task: Optional[Task] = None
        self.total_tasks_completed: int = 0

    def is_available(self) -> bool:
        """Verifica si el agente está libre (sin tarea asignada)."""
        return self.current_task is None

    def release(self):
        """Libera al agente de su tarea actual."""
        self.current_task = None

    def reset(self):
        """Resetea el estado del agente para una nueva simulación."""
        self.release()
        self.total_tasks_completed = 0

    def step(self):
        """Método abstracto que debe ser implementado por subclases."""
        raise NotImplementedError("El método step() debe ser implementado en la subclase.")

    def __repr__(self):
        """Representación textual del agente base."""
        task_id = self.current_task.id if self.current_task else "None"
        # self.unique_id es asignado por Mesa al añadir al schedule
        uid = getattr(self, 'unique_id', 'N/A')
        return f"{type(self).__name__}(unique_id={uid}, task={task_id})"


class TaskAgent(BaseProjectAgent):
    """Agente que representa un Recurso y ejecuta Tareas."""
    def __init__(self, model: 'ProjectManagementModel', resource: Resource, efficiency: float = 1.0):
        """
        Inicializa un TaskAgent.

        Args:
            model: La instancia del modelo Mesa.
            resource: El objeto Resource asociado a este agente.
            efficiency: Factor de eficiencia base del agente (1.0 = normal).
        """
        super().__init__(model)
        if not isinstance(resource, Resource):
            raise TypeError("TaskAgent requiere una instancia válida de Resource.")
        self.resource = resource
        self.efficiency = max(0.1, efficiency) # Asegurar una eficiencia mínima > 0
        self.agent_log_id = f"Agent_{self.resource.id}_{self.resource.name}" # ID para logging

    def assign_task(self, task: Task):
        """Asigna una tarea al agente si está disponible."""
        if self.is_available() and isinstance(task, Task):
            self.current_task = task
            task.status = "in_progress"
            task.assigned_resource = self.resource # Marcar la tarea como asignada a este recurso
            # print(f"Debug ({self.agent_log_id}): Tarea {task.id} asignada.") # Descomentar para debug

    def _execute_task_logic(self, error_margin: float) -> Tuple[bool, float]:
        """
        Lógica interna para ejecutar un paso de trabajo en la tarea actual.
        Actualiza el progreso, duración real y estado de la tarea.
        Calcula el costo incurrido en este paso.

        Args:
            error_margin: Factor de variabilidad aleatoria en el progreso.

        Returns:
            Tuple[bool, float]: (si la tarea se completó en este paso, costo incurrido en este paso)
        """
        cost_incurred_this_step = 0.0
        task_completed_this_step = False

        if not self.current_task:
            return task_completed_this_step, cost_incurred_this_step

        # Obtener costo por hora del recurso asociado
        resource_cost_ph = getattr(self.resource, 'cost_per_hour', 0.0)

        # Manejar tareas con duración cero (hitos)
        if self.current_task.duration <= 0:
            if self.current_task.progress < 1.0:
                self.current_task.update_progress(1.0) # Completarla instantáneamente
                self.total_tasks_completed += 1
                task_completed_this_step = True
                print(f"Debug ({self.agent_log_id}): Hito {self.current_task.id} completado.")
            # Liberar la tarea inmediatamente después de marcarla como hecha
            task_ref = self.current_task
            self.release()
            if task_ref: task_ref.assigned_resource = None # Desasignar recurso
            return task_completed_this_step, 0.0 # Hitos no incurren en costo/tiempo en este modelo

        # Calcular costo incurrido en este paso (asumiendo 1 paso = 1 hora)
        cost_incurred_this_step = resource_cost_ph

        # Calcular incremento de progreso basado en duración, eficiencia y aleatoriedad
        # El incremento representa qué fracción de la tarea se completa en 1 hora (paso)
        base_progress_per_step = (1.0 / max(1.0, self.current_task.duration)) # Progreso si eficiencia=1 y sin error
        actual_progress_this_step = base_progress_per_step * self.efficiency * (1 + random.uniform(-error_margin, error_margin))

        # Actualizar progreso y duración real de la tarea
        self.current_task.update_progress(actual_progress_this_step)
        if hasattr(self.current_task, 'real_duration'):
            self.current_task.real_duration += 1 # Incrementar duración real en 1 hora (paso)

        # Verificar si la tarea se completó
        if self.current_task.progress >= 1.0:
            self.total_tasks_completed += 1
            task_completed_this_step = True
            # print(f"Debug ({self.agent_log_id}): Tarea {self.current_task.id} completada.") # Descomentar para debug
            # Guardar referencia, liberar agente y desasignar recurso de la tarea
            task_ref = self.current_task
            self.release()
            if task_ref: task_ref.assigned_resource = None

        return task_completed_this_step, cost_incurred_this_step

    # MODIFICADO: Lógica de búsqueda y asignación de tareas
    def step(self):
        """Acción del TaskAgent en cada paso de tiempo: buscar tarea o trabajar."""

        # 1. Si el agente está libre, buscar una nueva tarea adecuada
        if self.is_available():
            if hasattr(self.model, 'project') and self.model.project:
                candidate_task: Optional[Task] = None
                agent_resource_id = self.resource.id # ID del recurso que este agente representa

                # Iterar por TODAS las tareas del proyecto para encontrar una adecuada
                for task in self.model.project.tasks.values():
                    # Condiciones para que una tarea sea candidata:
                    # a) Está 'to-do'
                    # b) No está asignada a ningún otro recurso/agente
                    # c) Requiere el recurso específico de ESTE agente (¡NUEVO!)
                    # d) Todas sus dependencias están 'done'
                    if (task.status == "to-do" and
                        task.assigned_resource is None and
                        hasattr(task, 'required_resource_id') and # Asegura que el campo exista
                        task.required_resource_id == agent_resource_id and # Coincidencia de rol/recurso
                        all(dep.status == "done" for dep in task.dependencies)): # Dependencias cumplidas

                        candidate_task = task
                        break # Encontré la primera tarea adecuada, no necesito seguir buscando

                # Si se encontró una tarea candidata, asignarla
                if candidate_task:
                    self.assign_task(candidate_task)

        # 2. Si el agente NO está libre (tiene tarea asignada), ejecutarla
        if not self.is_available():
            if hasattr(self.model, 'params') and self.model.params:
                # Ejecutar la lógica de trabajo de la tarea
                self._execute_task_logic(self.model.params.error_margin)
            else:
                 print(f"Error ({self.agent_log_id}): Modelo no tiene parámetros 'params' para ejecutar tarea.")

    def __repr__(self):
        """Representación textual del TaskAgent."""
        task_id = self.current_task.id if self.current_task else "None"
        uid = getattr(self, 'unique_id', 'N/A')
        return f"TaskAgent(uid={uid}, res_id={self.resource.id}, name='{self.resource.name}', task={task_id})"