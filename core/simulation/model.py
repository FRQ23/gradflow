# core/simulation/model.py
import random
from copy import deepcopy
from typing import List, Optional

# --- Importar Componentes de Mesa ESPECÍFICOS ---
from mesa import Model
from mesa.datacollection import DataCollector # Importar DataCollector
# --- Fin Importaciones Mesa ---

# --- Importar Componentes del Proyecto ---
# (Usando importaciones relativas estándar dentro de un paquete)
try:
    from ..project import Project
    from ..entities import Resource, Task
    # TaskAgent / BaseProjectAgent ya heredan de mesa.Agent
    from ..agents import TaskAgent, BaseProjectAgent
except (ImportError, ValueError):
    # Fallback si la estructura o ejecución no soporta relativa
    print("Advertencia: Usando importaciones directas en model.py (Mesa).")
    from project import Project
    from entities import Resource, Task
    from agents import TaskAgent, BaseProjectAgent
# Importar parámetros desde el mismo subpaquete 'simulation'
from .parameters import SimulationParameters
# --- Fin Importaciones Proyecto ---


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
        super().__init__() # Importante: Inicializar clase base de Mesa
        # Validaciones de entrada
        if not isinstance(base_project, Project): raise TypeError("base_project debe ser Project.")
        if not base_project.resources: raise ValueError("Project base debe tener Recursos.")
        if not isinstance(params, SimulationParameters): raise TypeError("params debe ser SimulationParameters.")

        self.params = params
        # El proyecto es el entorno compartido (copiado para esta simulación)
        self.project = deepcopy(base_project)
        self.project.reset_project_state() # Asegurar estado inicial limpio

        # --- Scheduler y Agentes ---
        self.schedule = RandomActivation(self) # Usar scheduler importado
        self.num_agents = 0
        for resource in self.project.get_all_resources():
            # Eficiencia podría ser más sofisticada (ej. basada en tipo de recurso/tarea)
            agent_efficiency = random.uniform(0.8, 1.2)
            # Usar ID del recurso como unique_id del agente Mesa
            agent = TaskAgent(unique_id=resource.id, model=self,
                              resource=resource, efficiency=agent_efficiency)
            self.schedule.add(agent) # Añadir al scheduler de Mesa
            self.num_agents += 1
        # print(f"Info (MesaModel): {self.num_agents} agentes creados.") # Log opcional

        # --- DataCollector de Mesa ---
        self.cumulative_actual_cost = 0.0 # AC se acumula aquí

        # Usar DataCollector importado
        self.datacollector = DataCollector(
            model_reporters={
                # Clave: Nombre de la columna en el DataFrame
                # Valor: Función (lambda) que toma el modelo (m) y devuelve la métrica
                "Time": lambda m: m.schedule.steps, # Tiempo = Pasos del scheduler
                "Completion": lambda m: m._calculate_completion_percent(),
                "EarnedValue": lambda m: m._calculate_earned_value(),
                "ActualCost": lambda m: m.cumulative_actual_cost, # Reportar AC acumulado
                "CPI": lambda m: m._calculate_cpi(),
                "ActiveAgents": lambda m: m._count_active_agents(),
                # "StepCost": lambda m: m.last_step_cost # Podría añadirse si calculamos y guardamos el costo del último paso
            }
            # Se pueden añadir agent_reporters si se necesitan métricas por agente
            # agent_reporters={"TasksDone": "total_tasks_completed"}
        )

        # Atributo 'running' es usado por herramientas como BatchRunner de Mesa
        self.running = True
        # Recolectar estado inicial (tiempo/paso 0)
        self.datacollector.collect(self)


    # --- Funciones auxiliares para DataCollector ---
    def _calculate_completion_percent(self) -> float:
        """Calcula % de completitud basado en progreso ponderado por duración."""
        if not self.project.tasks: return 100.0
        tasks_wd = [t for t in self.project.tasks.values() if t.duration > 0]
        if not tasks_wd: return 100.0 if all(t.progress>=1.0 for t in self.project.tasks.values()) else 0.0
        total_dur = sum(t.duration for t in tasks_wd)
        comp_dur = sum(t.duration * t.progress for t in tasks_wd)
        # Evitar división por cero si total_dur es 0 o negativo (aunque filtrado)
        return min(100.0, (comp_dur / total_dur) * 100) if total_dur > 0 else 100.0

    def _calculate_earned_value(self) -> float:
        """Calcula Valor Ganado (EV) acumulado."""
        # EV = Suma(Costo Estimado Tarea * % Progreso Tarea)
        return sum((task.estimated_cost or 0.0) * task.progress
                   for task in self.project.tasks.values())

    def _calculate_current_step_cost(self) -> float:
        """Calcula costo incurrido por agentes activos en el estado actual."""
        # Nota: Este cálculo se hace *antes* de que los agentes actúen en el paso actual.
        # Refleja el costo incurrido en el paso *anterior* si se llama al inicio de step().
        # O el costo del paso *actual* si se llama después de schedule.step() y los agentes
        # no se liberan inmediatamente al terminar. Para AC acumulado preciso,
        # es mejor sumar los costos devueltos por agent.execute_task como hicimos antes.
        # --> Vamos a mantener el AC acumulado basado en el retorno de execute_task (implícito antes).
        # --> Este método auxiliar no se usará directamente para el reporter 'ActualCost'.
        # --> Podría usarse para el reporter 'StepCost' si se desea.
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
        # Si AC es 0: si EV también es 0, CPI es indefinido (podemos devolver 0 o 1).
        # Si EV > 0, CPI es infinito (muy buena eficiencia inicial).
        elif ev > 0: return float('inf')
        else: return 0.0 # O 1.0 si se prefiere para EV=0, AC=0

    def _count_active_agents(self) -> int:
         """Cuenta agentes que no están disponibles (tienen tarea)."""
         return sum(1 for agent in self.schedule.agents if not agent.is_available())
    # --- Fin Funciones Auxiliares ---


    # --- MÉTODO STEP PRINCIPAL DE MESA ---
    def step(self):
        """Avanza el modelo un paso de tiempo ejecutando el scheduler y recolectando datos."""

        # --- Lógica PRE-activación de agentes ---
        # 1. Acumular Costo del Paso Anterior (o actual si se prefiere)
        #    Para mantener consistencia con el AC acumulado, calcularemos el costo
        #    generado DURANTE la activación de agentes en este paso.
        step_generated_cost = 0.0

        # 2. Lógica del Modelo (ej. reasignación periódica)
        if self.params.reassignment_frequency > 0 and \
           self.schedule.steps > 0 and \
           self.schedule.steps % self.params.reassignment_frequency == 0:
            self._reassign_tasks() # Modifica estado de agentes/tareas

        # --- Activación de Agentes ---
        # 3. Llama al método step() de cada agente según el planificador (RandomActivation)
        #    IMPORTANTE: El método TaskAgent.step() ahora contiene la lógica de
        #    buscar tarea (si está libre) y ejecutarla (si está ocupado).
        #    Necesitamos recoger el costo generado por execute_task.
        #    Modificaremos el scheduler.step() para recoger costos (requiere scheduler custom o iteración manual).
        #    Alternativa más simple: Iterar agentes aquí y llamar a step(), recogiendo costo.

        # --- Alternativa: Bucle Manual para recoger costos ---
        # self.schedule.step() # <- Reemplazado por bucle manual si necesitamos retorno de agent.step
        agent_list = self.schedule.agents # Obtener lista (o usar iterador)
        if isinstance(self.schedule, mesa.time.RandomActivation):
             random.shuffle(agent_list) # Emular RandomActivation si es necesario

        for agent in agent_list:
             cost_incurred_by_agent = 0.0
             if hasattr(agent, 'step') and callable(agent.step):
                  # Modificar agent.step para que DEVUELVA el costo incurrido?
                  # O agent.execute_task ya devuelve el costo? Revisemos agents.py...
                  # Sí, _execute_task_logic devuelve (bool, cost). Modifiquemos agent.step.

                  # ====> NECESITA MODIFICACIÓN en agents.py <====
                  # TaskAgent.step() debería llamar a _execute_task_logic y devolver el costo.
                  # Vamos a asumir que se modificó agents.py para esto (lo haremos después).
                  # Por ahora, simulamos llamando a execute_task aquí si está ocupado.
                  if not agent.is_available():
                       if isinstance(agent, TaskAgent):
                            _, cost_incurred = agent._execute_task_logic(self.params.error_margin)
                            step_generated_cost += cost_incurred
                  # La lógica de buscar tarea si está libre ya estaría en agent.step() que es llamado por schedule.step()
                  # Este bucle manual es INCORRECTO si usamos schedule.step().

        # --- Corrección: Usar schedule.step() y calcular costo DESPUÉS ---
        self.schedule.step() # <-- Llama a TaskAgent.step() para todos.

        # Calcular costo DESPUÉS de que actuaron, basado en quién trabajó
        # (Este método sigue siendo una aproximación si el agente se libera justo al final)
        # Una mejor forma sería que DataCollector recoja un atributo 'cost_this_step' del agente.
        step_cost_calculated_after = self._calculate_current_step_cost()
        self.cumulative_actual_cost += step_cost_calculated_after


        # --- Lógica POST-activación de agentes ---
        # 4. Recolectar datos para DataCollector
        #    Las funciones lambda usarán el estado actual del modelo y agentes.
        self.datacollector.collect(self)

        # 5. Avanzar tiempo del proyecto (si aún se quiere mantener sincronizado)
        #    Opcional, ya que usamos self.schedule.steps
        # self.project.update_project_status() # Puede eliminarse

        # 6. Comprobar parada (Mesa puede hacerlo automáticamente si se usa BatchRunner)
        if self.is_simulation_complete():
           self.running = False # Detiene BatchRunner/Server


    def _reassign_tasks(self):
        """Libera agentes y devuelve tareas a 'to-do'."""
        # print(f"Info (MesaModel): Reasignación en t={self.schedule.steps}")
        for agent in self.schedule.agents:
             if isinstance(agent, TaskAgent) and agent.current_task:
                task = agent.current_task
                task.status = "to-do"; task.assigned_resource = None
                agent.release()


    def is_simulation_complete(self) -> bool:
        """Verifica condiciones de término."""
        # (Sin cambios respecto a la versión anterior, usa schedule.steps)
        # if self.schedule.steps >= self.params.max_steps: return True # El runner controla esto
        if not self.project.tasks: return True
        if all(task.status == "done" for task in self.project.tasks.values()): return True
        no_available_tasks = self.project.get_next_available_task() is None
        all_agents_free = all(agent.is_available() for agent in self.schedule.agents)
        any_task_not_done = any(task.status != "done" for task in self.project.tasks.values())
        if any_task_not_done and no_available_tasks and all_agents_free:
             # print(f"Advertencia (MesaModel): Posible deadlock en t={self.schedule.steps}.")
             return True
        return False


    def __repr__(self):
        return (f"{type(self).__name__}(steps={self.schedule.steps}, "
                f"agents={len(self.schedule.agents)})")