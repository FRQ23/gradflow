# core/tools.py
import pandas as pd
from typing import List, Optional

# --- Importaciones ---
try:
    from .project import Project
    from .agents import Agent, TaskAgent
except (ImportError, ValueError):
    print("Advertencia: Usando importaciones directas en tools.py.")
    from project import Project
    from agents import Agent, TaskAgent
# --- Fin Importaciones ---

class MetricsCollector:
    """Recopila y presenta métricas de simulación (incluyendo EVM)."""
    def __init__(self):
        self.simulation_data = []
        self.cumulative_actual_cost = 0.0

    def reset(self):
        self.simulation_data = []
        self.cumulative_actual_cost = 0.0

    def capture_snapshot(self, project: Project, agents: List[Agent], time_step: int, step_actual_cost: float):
        self.cumulative_actual_cost += step_actual_cost
        active_agents_count = sum(1 for agent in agents if not agent.is_available())
        earned_value = self._calculate_earned_value(project)
        cpi = 0.0
        if self.cumulative_actual_cost > 0:
            safe_ev = earned_value if pd.notna(earned_value) else 0.0
            cpi = safe_ev / self.cumulative_actual_cost
        elif earned_value > 0: cpi = float('inf')
        completion_percent = self._calculate_completion_percent(project)
        metrics = {
            'time_step': time_step, 'completion_percent': completion_percent,
            'earned_value (EV)': earned_value, 'actual_cost (AC)': self.cumulative_actual_cost,
            'cost_performance_index (CPI)': cpi, 'active_agents': active_agents_count,
            'step_cost': step_actual_cost
        }
        self.simulation_data.append(metrics)

    def _calculate_completion_percent(self, project: Project) -> float:
        if not project.tasks: return 100.0 # Considerar proyecto sin tareas como completo
        total_duration = sum(t.duration for t in project.tasks.values() if t.duration > 0)
        if total_duration <= 0: return 100.0 if all(t.progress >= 1.0 for t in project.tasks.values()) else 0.0
        completed_duration = sum(t.duration * t.progress for t in project.tasks.values() if t.duration > 0)
        return min(100.0, (completed_duration / total_duration) * 100)

    def _calculate_earned_value(self, project: Project) -> float:
        # EV = Suma(Costo Estimado Tarea * % Progreso Tarea)
        # Asegurarse que estimated_cost no sea None
        return sum( (task.estimated_cost if task.estimated_cost is not None else 0.0) * task.progress
                   for task in project.tasks.values() )

    def generate_report(self) -> pd.DataFrame:
        if not self.simulation_data:
             cols = ['time_step', 'completion_percent', 'earned_value (EV)', 'actual_cost (AC)',
                     'cost_performance_index (CPI)', 'active_agents', 'step_cost']
             return pd.DataFrame(columns=cols)
        return pd.DataFrame(self.simulation_data)

    def present_results(self, filename: Optional[str] = "simulation_summary.csv", print_summary: bool = True):
        """Genera reporte, opcionalmente guarda y/o imprime resumen."""
        report_df = self.generate_report()
        if report_df.empty: print("Info (Collector): No hay datos para presentar."); return report_df
        if filename:
            try:
                report_df.to_csv(filename, index=False)
                print(f"Info (Collector): Datos de la última simulación guardados en '{filename}'.")
            except Exception as e: print(f"Error (Collector): No se pudo guardar reporte en '{filename}': {e}")
        if print_summary:
            print("\n--- Resumen de Simulación (Última Ejecución) ---")
            try:
                last_row = report_df.iloc[-1]
                print(f"Pasos de Tiempo Totales: {last_row['time_step']}")
                print(f"Completitud Final: {last_row['completion_percent']:.2f}%")
                print(f"Valor Ganado Final (EV): {last_row['earned_value (EV)']:.2f}")
                print(f"Costo Actual Final (AC): {last_row['actual_cost (AC)']:.2f}")
                cpi_val = last_row['cost_performance_index (CPI)']
                if cpi_val == float('inf'): cpi_str = "Inf (EV > 0, AC = 0)"
                elif pd.isna(cpi_val) or abs(cpi_val) < 1e-9 : cpi_str = "0.00 (o N/A)"
                else: cpi_str = f"{cpi_val:.2f}"
                print(f"Índice de Desempeño del Costo (CPI): {cpi_str}")
            except IndexError: print("No hay datos suficientes para resumen.")
            except KeyError as ke: print(f"Error de clave al generar resumen: {ke}")
            print("------------------------------------------------")
        return report_df