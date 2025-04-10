# core/project.py
import os
import aspose.tasks as tasks # Necesario importar aquí ahora
from typing import Dict, List, Optional
from core.entities import Task, Resource # Asegurar que entities se importe bien

# La clase Project ahora también se encarga de la carga desde MPP
class Project:
    def __init__(self):
        """Inicializa un proyecto vacío."""
        self.tasks: Dict[int, Task] = {} # UID -> Task
        self.resources: Dict[int, Resource] = {} # resource_id -> Resource
        self.current_time = 0
        self.baseline_cost = 0.0
        # El nombre del proyecto podría venir del MPP
        self.project_name: Optional[str] = None

    # --- Métodos de Carga ---
    def load_from_mpp(self, file_path: str):
        """
        Carga tareas de trabajo y dependencias desde un archivo .mpp,
        poblando este objeto Project. Limpia tareas/recursos existentes.

        Args:
            file_path: Ruta al archivo .mpp.

        Raises:
            FileNotFoundError, ValueError, Exception
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"No se pudo encontrar el archivo MPP: {file_path}")

        # Limpiar estado actual antes de cargar
        self._clear_project_data()
        print(f"Info: Cargando proyecto desde '{file_path}'...")

        try:
            mpp = tasks.Project(file_path)
            self.project_name = getattr(mpp.root_task, 'name', os.path.basename(file_path))
        except Exception as e:
            raise ValueError(f"Fallo al cargar el archivo .mpp '{file_path}' usando Aspose.Tasks: {e}")

        # Usaremos un mapa temporal UID -> Task durante la carga
        task_map_during_load: Dict[int, Task] = {}

        # 1. Procesar Tareas Recursivamente
        try:
            # Iniciar recursión desde la tarea raíz del proyecto MPP
            self._process_mpp_task_recursive(mpp.root_task, task_map_during_load)
            # Asignar las tareas cargadas al diccionario principal del proyecto
            self.tasks = task_map_during_load
            print(f"Info: {len(self.tasks)} tareas de trabajo (no resumen) cargadas.")
        except Exception as e:
            print(f"Error Crítico durante el procesamiento recursivo de tareas MPP: {e}")
            raise ValueError(f"Error procesando tareas en '{file_path}': {e}")

        # 2. Procesar Dependencias
        try:
            added_deps = 0
            for link in mpp.task_links:
                if link.link_type != tasks.TaskLinkType.FINISH_TO_START:
                    continue

                pred_task_obj = getattr(link, 'pred_task', None)
                succ_task_obj = getattr(link, 'succ_task', None)
                if not pred_task_obj or not succ_task_obj: continue

                source_uid = getattr(pred_task_obj, 'uid', None)
                target_uid = getattr(succ_task_obj, 'uid', None)
                if source_uid is None or target_uid is None: continue

                # Añadir dependencia si ambas tareas (por UID) existen en nuestro mapa
                if target_uid in self.tasks and source_uid in self.tasks:
                    target_task_instance = self.tasks[target_uid]
                    source_task_instance = self.tasks[source_uid]

                    if not hasattr(target_task_instance, 'dependencies') or target_task_instance.dependencies is None:
                        target_task_instance.dependencies = []
                    if source_task_instance not in target_task_instance.dependencies:
                        target_task_instance.dependencies.append(source_task_instance)
                        added_deps += 1
            print(f"Info: {added_deps} dependencias Finish-to-Start añadidas.")

        except Exception as e:
             print(f"Error durante el procesamiento de dependencias MPP: {e}")
             raise ValueError(f"Error procesando dependencias de tareas en '{file_path}': {e}")

        # 3. (Opcional) Cargar Recursos del MPP (No implementado aquí aún)
        # self._load_resources_from_mpp(mpp)

        # 4. Calcular métricas base después de cargar
        self._calculate_baseline_metrics()
        print(f"Info: Carga completada. Costo base calculado: {self.baseline_cost:.2f}")


    def _process_mpp_task_recursive(self, mpp_task: tasks.Task, task_map_target: Dict[int, Task]):
        """
        Método auxiliar recursivo para procesar tareas MPP.
        Añade tareas de trabajo (no resumen) al task_map_target.
        (Lógica movida desde MPPReader)
        """
        try:
            task_id = mpp_task.id
            if task_id != 0: # Omitir detalles de la tarea raíz
                is_summary = getattr(mpp_task, 'is_summary', False)
                task_uid = getattr(mpp_task, 'uid', None)

                if task_uid is not None and not is_summary:
                    task_name = getattr(mpp_task, 'name', 'Unnamed Task')
                    task_cost = getattr(mpp_task, 'cost', 0.0)
                    duration_obj = getattr(mpp_task, 'duration', None)
                    duration_hours = 0.0
                    if duration_obj:
                        try:
                            time_span = duration_obj.time_span
                            if time_span:
                                total_seconds = time_span.total_seconds()
                                if total_seconds >= 0: duration_hours = total_seconds / 3600
                        except Exception: pass

                    try:
                        # Usar la clase Task definida en entities.py
                        new_task = Task(
                            task_id=task_uid, name=task_name if task_name else "Unnamed Task",
                            duration=duration_hours,
                            estimated_cost=float(task_cost) if task_cost is not None else 0.0
                        )
                        task_map_target[task_uid] = new_task # Añadir al mapa temporal
                    except Exception as e:
                        print(f"Advertencia: Error al crear objeto Task para UID={task_uid}: {e}")
        except Exception as e:
            print(f"Advertencia: Error procesando detalles de tarea MPP (ID: {mpp_task.id if mpp_task else 'N/A'}): {e}")

        # Procesar Hijas recursivamente
        try:
            for child_task in mpp_task.children:
                 self._process_mpp_task_recursive(child_task, task_map_target)
        except Exception as e:
            print(f"Advertencia: Error al obtener/iterar hijas de tarea MPP (ID: {mpp_task.id if mpp_task else 'N/A'}): {e}")


    # --- Métodos existentes (modificados/añadidos previamente) ---

    def add_task(self, task: Task):
        """Añade o actualiza una tarea en el proyecto usando su UID como clave."""
        if not isinstance(task, Task):
             raise TypeError("Solo se pueden añadir objetos Task.")
        self.tasks[task.id] = task

    def add_resource(self, resource: Resource):
        """Añade o actualiza un recurso en el proyecto."""
        if not isinstance(resource, Resource):
            raise TypeError("Solo se pueden añadir objetos Resource.")
        self.resources[resource.id] = resource

    def get_resource(self, resource_id: int) -> Optional[Resource]:
        return self.resources.get(resource_id)

    def get_all_resources(self) -> List[Resource]:
        return list(self.resources.values())

    def _calculate_baseline_metrics(self):
        if self.tasks:
             self.baseline_cost = sum(task.estimated_cost for task in self.tasks.values())
        else:
             self.baseline_cost = 0.0

    def get_next_available_task(self) -> Optional[Task]:
        for task in self.tasks.values():
            if task.status == "to-do" and task.assigned_resource is None:
                deps_ready = all(dep.status == "done" for dep in task.dependencies)
                if deps_ready:
                    return task
        return None

    def update_project_status(self):
        self.current_time += 1

    def reset_project_state(self):
        self.current_time = 0
        for task in self.tasks.values():
            task.status = "to-do"
            task.progress = 0.0
            task.real_duration = 0.0
            task.assigned_resource = None

    def _clear_project_data(self):
        """Limpia los datos internos del proyecto."""
        self.tasks = {}
        self.resources = {}
        self.current_time = 0
        self.baseline_cost = 0.0
        self.project_name = None