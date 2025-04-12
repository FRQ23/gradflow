# core/entities.py
from typing import List, Dict, Optional

# Clase Task
class Task:
    def __init__(self, task_id: int, name: str, duration: float, estimated_cost: float):
        self.id = task_id # UID de MPP/MPXJ
        self.name = name
        self.duration = max(0.0, duration) # Duración planificada
        self.estimated_cost = max(0.0, estimated_cost) # Costo planificado (BCWS)
        self.status: str = "to-do" # Estado: to-do, in_progress, done
        self.progress: float = 0.0 # Progreso (0.0 a 1.0)
        self.real_duration: float = 0.0 # Duración real acumulada en simulación
        self.dependencies: List[Task] = [] # Lista de tareas predecesoras
        self.assigned_resource: Optional['Resource'] = None # Recurso actualmente asignado (en simulación)
        # NUEVO: Campo para almacenar el ID del recurso requerido según el plan (MPP)
        self.required_resource_id: Optional[int] = None

    def update_progress(self, increment: float):
        """Actualiza el progreso de la tarea, asegurando que no supere 1.0 y actualiza estado a 'done'."""
        if self.status == "done": return
        self.progress = min(1.0, max(0.0, self.progress + increment))
        if self.progress >= 1.0:
            self.status = "done"

    def __repr__(self):
        """Representación textual de la tarea."""
        deps_str = f" deps={[d.id for d in self.dependencies]}" if self.dependencies else ""
        # MODIFICADO: Incluir el recurso requerido si existe
        req_res_str = f" req_res={self.required_resource_id}" if self.required_resource_id is not None else ""
        # MODIFICADO: Mostrar el recurso asignado si existe
        assigned_res_str = f" assigned={self.assigned_resource.id}" if self.assigned_resource else ""
        return (f"Task(id={self.id}, '{self.name}', dur={self.duration:.1f}h, "
                f"cost={self.estimated_cost:.2f}, status='{self.status}', "
                f"prog={self.progress*100:.0f}%, real_dur={self.real_duration:.1f}h"
                f"{req_res_str}{assigned_res_str}{deps_str})")


# Clase Resource (Sin cambios estructurales necesarios aquí para los requisitos)
class Resource:
    """Representa un recurso (ej. persona, equipo) con un costo."""
    def __init__(self, resource_id: int, name: str, cost_per_hour: float):
        self.id = resource_id # ID único del recurso (de MPP o config)
        self.name = name
        self.cost_per_hour = max(0.0, cost_per_hour)
        # Podrían añadirse más atributos como disponibilidad, eficiencia base, etc.

    def __repr__(self):
        return f"Resource(id={self.id}, name='{self.name}', cost/h={self.cost_per_hour:.2f})"