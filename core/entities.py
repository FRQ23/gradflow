# core/entities.py
from typing import List, Dict, Optional

# Clase Task (Asegúrate que esté como la definimos antes)
class Task:
    def __init__(self, task_id: int, name: str, duration: float, estimated_cost: float):
        self.id = task_id # Este es el UID que viene de MPP/MPXJ
        self.name = name
        self.duration = max(0.0, duration)
        self.estimated_cost = max(0.0, estimated_cost)
        self.status: str = "to-do"
        self.progress: float = 0.0
        self.real_duration: float = 0.0
        self.dependencies: List[Task] = []
        self.assigned_resource: Optional['Resource'] = None

    def update_progress(self, increment: float):
        if self.status == "done": return
        self.progress = min(1.0, max(0.0, self.progress + increment))
        if self.progress >= 1.0: self.status = "done"

    def __repr__(self):
        deps_str = f" deps={[d.id for d in self.dependencies]}" if self.dependencies else ""
        res_str = f" res={self.assigned_resource.id}" if self.assigned_resource else ""
        return (f"Task(id={self.id}, '{self.name}', dur={self.duration:.1f}h, "
                f"cost={self.estimated_cost:.2f}, status='{self.status}', "
                f"prog={self.progress*100:.0f}%, real_dur={self.real_duration:.1f}{deps_str}{res_str})")

# --- CLASE RESOURCE - VERIFICAR ESTA PARTE ---
class Resource:
    """Representa un recurso (ej. persona, equipo) con un costo."""
    # ASEGÚRATE QUE EL PRIMER ARGUMENTO SEA 'resource_id'
    def __init__(self, resource_id: int, name: str, cost_per_hour: float):
        # Internamente puedes seguir llamando al atributo self.id si prefieres,
        # pero el PARÁMETRO del constructor debe ser 'resource_id'
        self.id = resource_id # <--- Asigna el parámetro resource_id al atributo id
        self.name = name
        self.cost_per_hour = max(0.0, cost_per_hour)
        # Podrías añadir más atributos como disponibilidad, eficiencia base, etc.
        # self.assigned_tasks: List[Task] = [] # Opcional

    def __repr__(self):
        # Usar self.id para mostrarlo está bien
        return f"Resource(id={self.id}, name='{self.name}', cost/h={self.cost_per_hour:.2f})"
# --- FIN CLASE RESOURCE ---