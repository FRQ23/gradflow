# core/simulation/parameters.py
from dataclasses import dataclass

@dataclass
class SimulationParameters:
    # num_agents: int = 5 # Eliminado - ahora se basa en los recursos del proyecto
    error_margin: float = 0.1
    reassignment_frequency: int = 10 # 0 o negativo para desactivar reasignación
    max_steps: int = 1000 # Aumentar un poco los pasos máximos podría ser útil