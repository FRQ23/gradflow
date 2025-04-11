# core/simulation/model.py
import random
from copy import deepcopy


# --- Importar Componentes de Mesa ---
from mesa import Model
from mesa.time import RandomActivation
from mesa.datacollection import DataCollector
# --- Fin Importaciones Mesa ---

# --- Importar Componentes del Proyecto (Absolutos desde 'core') ---
from core.project import Project
from core.entities import Resource, Task
from core.agents import TaskAgent, BaseProjectAgent
from core.simulation.parameters import SimulationParameters # <-- Importación Absoluta
# --- Fin Importaciones ---


# Heredar de mesa.Model importado
class ProjectManagementModel(Model):
    """
    Modelo de simulación basado en Mesa para gestión de proyectos.
    Orquesta agentes, tareas y tiempo usando el scheduler y datacollector de Mesa.
    """
    def __init__(self, base_project: Project, params: SimulationParameters):
        """
        Inicializa el modelo Mesa.

        Args:
            base_project: El objeto Project base (cargado y con recursos).
            params: Parámetros de la simulación.
        """
        # --- LLAMADA A SUPER() ---
        super().__init__() # <-- ¡Llamada OBLIGATORIA al constructor de mesa.Model!
        # --- FIN LLAMADA A SUPER() ---

        # Validaciones de entrada
        if not isinstance(base_project, Project): raise TypeError("base_project debe ser Project.")
        if not base_project.resources: raise ValueError("Project base debe tener Recursos.")
        if not isinstance(params, SimulationParameters): raise TypeError("params debe ser SimulationParameters.")

        self.params = params
        self.project = deepcopy(base_project)
        self.project.reset_project_state() # Asegurar estado inicial limpio

        # --- Scheduler y Agentes ---
        self.schedule = RandomActivation(self) # Usar scheduler importado
        self.num_agents = 0
        for resource in self.project.get_all_resources():
            agent_efficiency = random.uniform(0.8, 1.2)

            # --- LÍNEA MODIFICADA (sin unique_id) ---
            # Mesa asignará unique_id automáticamente al hacer schedule.add()
            agent = TaskAgent(model=self,  # Solo model, resource y args específicos
                              resource=resource,
                              efficiency=agent_efficiency)
            # --- FIN LÍNEA MODIFICADA ---

            self.schedule.add(agent)  # Aquí Mesa le asigna el unique_id
            self.num_agents += 1
        # print(f"Info (MesaModel): {self.num_agents} agentes creados.")


        # --- DataCollector de Mesa ---
        self.cumulative_actual_cost = 0.0 # AC se acumula aquí
        self.datacollector = DataCollector(
            model_reporters={
                "Time": lambda m: m.schedule.steps,
                "Completion": lambda m: m._calculate_completion_percent(),
                "EarnedValue": lambda m: m._calculate_earned_value(),
                "ActualCost": lambda m: m.cumulative_actual_cost,
                "CPI": lambda m: m._calculate_cpi(),
                "ActiveAgents": lambda m: m._count_active_agents(),
            }
            # agent_reporters={...} # Opcional
        )
        self.running = True
        self.datacollector.collect(self) # Coleccionar estado inicial (t=0)

    # --- Funciones auxiliares para DataCollector ---
    def _calculate_completion_percent(self) -> float:
        if not self.project.tasks: return 100.0
        tasks_wd = [t for t in self.project.tasks.values() if t.duration > 0]
        if not tasks_wd: return 100.0 if all(t.progress>=1.0 for t in self.project.tasks.values()) else 0.0
        total_dur = sum(t.duration for t in tasks_wd)
        comp_dur = sum(t.duration * t.progress for t in tasks_wd)
        return min(100.0, (comp_dur / total_dur) * 100) if total_dur > 0 else 100.0

    def _calculate_earned_value(self) -> float:
        return sum((task.estimated_cost or 0.0) * task.progress for task in self.project.tasks.values())

    def _calculate_current_step_cost(self) -> float:
        """Calcula costo incurrido por agentes activos en el estado actual (aproximación)."""
        step_cost = 0.0
        for agent in self.schedule.agents:
             if isinstance(agent, TaskAgent) and not agent.is_available() and \
                hasattr(agent, 'resource') and agent.resource and \
                hasattr(agent.resource, 'cost_per_hour'):
                 step_cost += agent.resource.cost_per_hour
        return step_cost

    def _calculate_cpi(self) -> float:
        """Calcula CPI (EV/AC), manejando ceros."""
        ev = self._calculate_earned_value()
        ac = self.cumulative_actual_cost
        if ac > 0: return ev / ac
        elif ev > 0: return float('inf')
        else: return 0.0

    def _count_active_agents(self) -> int:
         """Cuenta agentes que no están disponibles (tienen tarea)."""
         return sum(1 for agent in self.schedule.agents if not agent.is_available())
    # --- Fin Funciones Auxiliares ---

    # --- MÉTODO STEP PRINCIPAL DE MESA ---
    def step(self):
        """Avanza el modelo un paso de tiempo."""
        step_cost = self._calculate_current_step_cost()
        self.cumulative_actual_cost += step_cost
        # Ya NO se llama a self.project.update_project_status()
        if self.params.reassignment_frequency > 0 and \
           self.schedule.steps > 0 and \
           self.schedule.steps % self.params.reassignment_frequency == 0:
            self._reassign_tasks()
        self.schedule.step() # <-- Llama a agent.step() y avanza self.schedule.steps
        self.datacollector.collect(self) # Recolecta datos DESPUÉS de actuar
        if self.is_simulation_complete(): self.running = False

    # --- Otros métodos (_reassign_tasks, is_simulation_complete, __repr__) ---
    def _reassign_tasks(self):
        for agent in self.schedule.agents:
             if isinstance(agent, TaskAgent) and agent.current_task:
                task = agent.current_task; task.status = "to-do"; task.assigned_resource = None; agent.release()

    def is_simulation_complete(self) -> bool:
        if not self.project.tasks: return True
        if all(task.status == "done" for task in self.project.tasks.values()): return True
        no_available_tasks = self.project.get_next_available_task() is None
        all_agents_free = all(agent.is_available() for agent in self.schedule.agents)
        any_task_not_done = any(task.status != "done" for task in self.project.tasks.values())
        if any_task_not_done and no_available_tasks and all_agents_free: return True
        return False

    def __repr__(self):
        return (f"{type(self).__name__}(steps={self.schedule.steps}, agents={len(self.schedule.agents)})")