# core/simulation/model.py

import random
from copy import deepcopy
from typing import List, Optional

# --- Importaciones (como estaban) ---
try:
    from ..project import Project
    from ..entities import Resource
    from ..agents import TaskAgent, Agent
    from ..tools import MetricsCollector # Importar Collector
except (ImportError, ValueError):
    print("Advertencia: Falló importación relativa en model.py. Intentando importación directa.")
    from project import Project
    from entities import Resource
    from agents import TaskAgent, Agent
    from tools import MetricsCollector
# --- Fin Importaciones ---

from core.simulation.parameters import SimulationParameters

class ProjectManagementModel:
    # ... (__init__ sin cambios) ...
    def __init__(self, base_project: Project, params: SimulationParameters):
        if not base_project.resources:
            raise ValueError("El objeto 'base_project' debe contener Recursos.")
        self.project = deepcopy(base_project)
        self.project.reset_project_state()
        self.params = params
        self.time_step = 0
        self.agents: List[TaskAgent] = []
        available_resources = self.project.get_all_resources()
        for resource in available_resources:
            agent_efficiency = random.uniform(0.8, 1.2)
            self.agents.append(TaskAgent(resource=resource, efficiency=agent_efficiency))


    # --- MÉTODO STEP MODIFICADO ---
    def step(self, collector: MetricsCollector):
        self.time_step += 1
        current_step_total_cost = 0.0 # <-- Acumulador para el costo del paso

        # 1. Reasignación (sin cambios)
        if self.params.reassignment_frequency > 0 and \
           self.time_step > 0 and \
           self.time_step % self.params.reassignment_frequency == 0:
            self._reassign_tasks()

        # 2. Asignación (sin cambios)
        available_agents = [agent for agent in self.agents if agent.is_available()]
        if available_agents:
            for agent in available_agents:
                 task = self.project.get_next_available_task()
                 if task:
                     agent.assign_task(task)
                 else:
                     break

        # 3. Ejecución (MODIFICADO para recoger costo)
        for agent in self.agents:
            if not agent.is_available():
                 if isinstance(agent, TaskAgent):
                     # execute_task ahora devuelve (completed, cost)
                     _, cost_incurred = agent.execute_task(self.params.error_margin)
                     # Acumular el costo devuelto por el agente
                     current_step_total_cost += cost_incurred
                 # else: Lógica para otros tipos de agentes si los hubiera

        # 4. Actualizar Estado Proyecto (sin cambios)
        self.project.update_project_status()

        # 5. Capturar Snapshot (MODIFICADO para pasar costo calculado)
        collector.capture_snapshot(
            project=self.project,
            agents=self.agents,
            time_step=self.time_step,
            step_actual_cost=current_step_total_cost # <-- Pasar costo acumulado del paso
        )
    # --- FIN MÉTODO STEP MODIFICADO ---

    # ... (_reassign_tasks, is_simulation_complete sin cambios) ...
    def _reassign_tasks(self):
        # print(f"Info (Modelo): Realizando reasignación en t={self.time_step}")
        for agent in self.agents:
            if agent.current_task:
                task = agent.current_task
                task.status = "to-do"
                task.assigned_resource = None
                agent.release()

    def is_simulation_complete(self, max_steps: Optional[int] = None) -> bool:
        if max_steps is not None and self.time_step >= max_steps: return True
        if not self.project.tasks or all(task.status == "done" for task in self.project.tasks.values()): return True
        no_available_tasks = self.project.get_next_available_task() is None
        all_agents_free = all(agent.is_available() for agent in self.agents)
        any_task_not_done = any(task.status != "done" for task in self.project.tasks.values())
        if any_task_not_done and no_available_tasks and all_agents_free:
             print(f"Advertencia (Modelo): Simulación detenida en t={self.time_step}. Posible deadlock.")
             return True
        return False