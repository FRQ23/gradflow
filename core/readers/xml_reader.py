# core/readers/xml_reader.py
import os
import traceback
from typing import Dict, Optional, Tuple
from lxml import etree # Usar lxml para parsear XML
import isodate # Para parsear duraciones ISO 8601 (ej. PT8H0M0S)
from decimal import Decimal, InvalidOperation # Para manejar costos

# --- Importaciones del Proyecto Core ---
from core.project import Project
from core.entities import Task, Resource
from .base_reader import ProjectReader
# --- Fin Importaciones Core ---

# Constantes para tipos (según estándar MS Project XML)
# --- CORRECCIÓN REALIZADA AQUÍ ---
XML_RESOURCE_TYPE_WORK = 1       # << CORRECTED: WORK resources are Type 1 in MS Project XML
XML_RESOURCE_TYPE_MATERIAL = 0   # << CORRECTED (for completeness): Material resources are typically Type 0
# --- FIN CORRECCIÓN ---
XML_TASK_LINK_TYPE_FS = 1        # Finish-to-Start (This was already correct)

class XmlProjectReader(ProjectReader):
    """
    Lector de archivos de proyecto en formato XML de Microsoft Project usando lxml.
    Extrae Tareas, Recursos (solo tipo Trabajo), Asignaciones y Dependencias FS.
    """

    def _get_namespace(self, element) -> Optional[str]:
        """Intenta extraer el namespace principal del elemento raíz del XML."""
        if element.nsmap and None in element.nsmap:
            return element.nsmap[None]
        # Intenta buscar un namespace común si no hay uno por defecto
        for ns in element.nsmap.values():
            if 'schemas.microsoft.com/project' in ns:
                return ns
        print("Advertencia (XmlReader): No se pudo determinar el namespace principal del XML.")
        return None # No se pudo determinar

    def _parse_xml_duration_hours(self, duration_str: Optional[str]) -> float:
        """Convierte duración en formato ISO 8601 (ej. PT8H0M0S) a horas."""
        if not duration_str:
            return 0.0
        try:
            # isodate parsea el formato PT...
            duration_delta = isodate.parse_duration(duration_str)
            # Convertir timedelta a horas totales
            return duration_delta.total_seconds() / 3600.0
        except (isodate.ISO8601Error, TypeError, ValueError) as e:
            print(f"Adv (XmlReader): No se pudo parsear duración '{duration_str}': {e}")
            return 0.0

    def _parse_xml_cost(self, cost_str: Optional[str]) -> float:
        """Convierte un string de costo a float."""
        if not cost_str:
            return 0.0
        try:
            # Intentar convertir directamente, asumiendo que es un número
            return float(cost_str)
        except (ValueError, TypeError):
            print(f"Adv (XmlReader): No se pudo convertir costo '{cost_str}' a float.")
            return 0.0

    def _parse_xml_cost_per_hour(self, rate_str: Optional[str]) -> float:
        """Intenta extraer costo por hora de un string (ej. "50/h"). Simple."""
        if not rate_str:
            return 0.0
        try:
            # Asumir formato simple NUMERO/h o solo NUMERO (interpretado como por hora)
            if '/h' in rate_str.lower():
                rate_str = rate_str.lower().replace('/h', '')
            return float(rate_str.strip())
        except (ValueError, TypeError):
             print(f"Adv (XmlReader): No se pudo extraer costo/hora de '{rate_str}'. Asumiendo 0.")
             return 0.0

    def load(self, file_path: str) -> Project:
        """
        Carga el proyecto desde un archivo XML de MS Project.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"XmlReader: Archivo no encontrado: {file_path}")

        print(f"Info (XmlReader): Cargando proyecto desde '{file_path}'...")
        project = Project()
        project._clear_project_data()
        # Mapas para relacionar UIDs leídos del XML con objetos Python
        resource_uid_map: Dict[int, Resource] = {} # XML Resource UID -> Objeto Resource Python
        task_uid_map: Dict[int, Task] = {}       # XML Task UID -> Objeto Task Python

        try:
            # Parsear el archivo XML con lxml
            tree = etree.parse(file_path)
            root = tree.getroot()

            # Obtener el namespace para búsquedas XPath/find
            ns = self._get_namespace(root)
            if not ns:
                raise ValueError("No se pudo encontrar el namespace principal en el archivo XML.")
            # Crear mapa de namespace para XPath
            ns_map = {'p': ns}
            print(f"Info (XmlReader): Usando namespace: {ns}")

            # --- 1. Procesar Recursos ---
            resources_element = root.find(f'{{{ns}}}Resources')
            if resources_element is not None:
                print(f"Info (XmlReader): Procesando {len(resources_element)} recursos encontrados...")
                resources_processed = 0
                for res_elem in resources_element.findall(f'{{{ns}}}Resource'):
                    res_name = None
                    res_uid_val = None
                    res_id_val = None
                    res_type_val = None
                    try:
                        # Extraer datos básicos del recurso
                        res_uid_elem = res_elem.find(f'{{{ns}}}UID')
                        res_id_elem = res_elem.find(f'{{{ns}}}ID')
                        res_name_elem = res_elem.find(f'{{{ns}}}Name')
                        res_type_elem = res_elem.find(f'{{{ns}}}Type')

                        # Chequeos básicos
                        if res_uid_elem is None or res_id_elem is None: continue # UID e ID son necesarios
                        if res_uid_elem.text is None or res_id_elem.text is None: continue # Necesitan tener valor
                        res_uid_val = int(res_uid_elem.text)
                        res_id_val = int(res_id_elem.text)

                        res_name = res_name_elem.text if res_name_elem is not None else None
                        # Saltar recursos sin nombre (a menudo placeholders como ID 0)
                        if res_name is None and res_id_val == 0: continue # Saltar el recurso nulo interno si no tiene nombre
                        if res_name is None: res_name = f"Unnamed Resource ID {res_id_val}" # Darle un nombre si falta pero no es ID 0

                        # Chequear tipo (SOLO PROCESAR TIPO TRABAJO)
                        res_type_val = int(res_type_elem.text) if res_type_elem is not None and res_type_elem.text is not None else -1
                        # --- USA LA CONSTANTE CORREGIDA ---
                        if res_type_val != XML_RESOURCE_TYPE_WORK: # WORK debe ser 1
                            # print(f"Debug: Recurso UID={res_uid_val} ID={res_id_val} es tipo {res_type_val}. Saltando (se esperaba {XML_RESOURCE_TYPE_WORK}).")
                            continue

                        # Extraer costo por hora (StandardRate)
                        std_rate_elem = res_elem.find(f'{{{ns}}}StandardRate')
                        cost_per_hour = self._parse_xml_cost_per_hour(std_rate_elem.text if std_rate_elem is not None else None)

                        # Crear objeto Resource Python (usando ID como resource_id)
                        py_resource = Resource(resource_id=res_id_val, name=res_name, cost_per_hour=cost_per_hour)
                        project.add_resource(py_resource)
                        # Mapear por UID del XML para las asignaciones
                        resource_uid_map[res_uid_val] = py_resource
                        resources_processed += 1
                        # print(f"  --> Recurso WORK Procesado: UID={res_uid_val}, ID={res_id_val}, Nombre='{res_name}', Costo/h={cost_per_hour:.2f}")

                    except (ValueError, TypeError, AttributeError) as res_e:
                         print(f"Adv (XmlReader): Error procesando recurso XML (UID={res_uid_val}, ID={res_id_val}, Nombre='{res_name}'): {res_e}")
                         # traceback.print_exc() # Descomentar para depurar

                print(f"Info (XmlReader): {resources_processed} recursos de tipo WORK procesados.")
                if resources_processed == 0:
                    # Esta advertencia ahora solo debería aparecer si REALMENTE no hay recursos tipo 1 en el XML
                    print("Advertencia: No se procesaron recursos de tipo WORK. La simulación podría no tener agentes.")

            else:
                 print("Advertencia: No se encontró la sección <Resources> en el XML.")


            # --- 2. Procesar Tareas ---
            tasks_element = root.find(f'{{{ns}}}Tasks')
            if tasks_element is not None:
                print(f"Info (XmlReader): Procesando {len(tasks_element)} tareas encontradas...")
                tasks_processed = 0
                for task_elem in tasks_element.findall(f'{{{ns}}}Task'):
                    task_name = None
                    task_uid_val = None
                    try:
                        # Extraer datos básicos de la tarea
                        task_uid_elem = task_elem.find(f'{{{ns}}}UID')
                        task_id_elem = task_elem.find(f'{{{ns}}}ID') # ID de MS Project
                        task_name_elem = task_elem.find(f'{{{ns}}}Name')
                        task_summary_elem = task_elem.find(f'{{{ns}}}Summary')
                        task_milestone_elem = task_elem.find(f'{{{ns}}}Milestone')

                        if task_uid_elem is None or task_uid_elem.text is None: continue # UID es esencial
                        task_uid_val = int(task_uid_elem.text)
                        if task_uid_val == 0: continue # Saltar tarea raíz UID 0 (resumen del proyecto)

                        # Saltar tareas resumen
                        is_summary = task_summary_elem is not None and task_summary_elem.text == '1'
                        if is_summary: continue

                        task_name = task_name_elem.text if task_name_elem is not None else f"Unnamed Task UID {task_uid_val}"

                        # Obtener duración y costo
                        duration_elem = task_elem.find(f'{{{ns}}}Duration')
                        duration_hours = self._parse_xml_duration_hours(duration_elem.text if duration_elem is not None else None)

                        # Manejar hitos (milestones) - usualmente tienen duración 0
                        is_milestone = task_milestone_elem is not None and task_milestone_elem.text == '1'
                        if is_milestone: duration_hours = 0.0

                        cost_elem = task_elem.find(f'{{{ns}}}Cost')
                        task_cost = self._parse_xml_cost(cost_elem.text if cost_elem is not None else None)

                        # Crear objeto Task Python (usando UID como task_id)
                        py_task = Task(task_id=task_uid_val, name=task_name,
                                       duration=duration_hours, estimated_cost=task_cost)

                        project.add_task(py_task)
                        task_uid_map[task_uid_val] = py_task
                        tasks_processed += 1

                    except (ValueError, TypeError, AttributeError) as task_e:
                         print(f"Adv (XmlReader): Error procesando tarea XML (UID={task_uid_val}, Nombre='{task_name}'): {task_e}")
                         # traceback.print_exc()

                print(f"Info (XmlReader): {tasks_processed} tareas de trabajo procesadas.")
                if tasks_processed == 0:
                     print("Error Crítico (XmlReader): No se cargaron tareas válidas.")
                     raise ValueError("Proyecto XML cargado no contiene tareas válidas.")
            else:
                 print("Error Crítico (XmlReader): No se encontró la sección <Tasks> en el XML.")
                 raise ValueError("Archivo XML no contiene sección <Tasks>.")


            # --- 3. Procesar Asignaciones ---
            assignments_element = root.find(f'{{{ns}}}Assignments')
            if assignments_element is not None:
                print(f"Info (XmlReader): Procesando {len(assignments_element)} asignaciones...")
                assignments_processed = 0
                for assign_elem in assignments_element.findall(f'{{{ns}}}Assignment'):
                    task_uid_assign = None
                    res_uid_assign = None
                    try:
                        task_uid_elem = assign_elem.find(f'{{{ns}}}TaskUID')
                        res_uid_elem = assign_elem.find(f'{{{ns}}}ResourceUID')

                        if task_uid_elem is None or res_uid_elem is None: continue
                        # Skip assignment if either UID is missing text content
                        if task_uid_elem.text is None or res_uid_elem.text is None: continue

                        task_uid_assign = int(task_uid_elem.text)
                        res_uid_assign = int(res_uid_elem.text)

                        # Buscar la tarea y el recurso Python correspondientes
                        # IMPORTANTE: Usamos los MAPAS creados antes (XML UID -> Objeto Python)
                        target_task = task_uid_map.get(task_uid_assign)
                        target_resource = resource_uid_map.get(res_uid_assign) # Busca por UID del XML

                        # Asignar solo si ambos existen y la tarea no tiene ya una asignación (tomamos la primera)
                        # Y si el recurso encontrado es realmente un recurso WORK (fue añadido al mapa)
                        if target_task and target_resource and target_task.required_resource_id is None:
                            # Guardamos el ID del recurso (no el UID del XML) en la tarea
                            target_task.required_resource_id = target_resource.id
                            assignments_processed += 1
                            # print(f"  Debug: Asignación Tarea UID {task_uid_assign} -> Recurso UID {res_uid_assign} (ID {target_resource.id})")
                        # else: # Debug
                            # if not target_task: print(f"Debug: Asignación saltada, Tarea UID {task_uid_assign} no encontrada en mapa.")
                            # if not target_resource: print(f"Debug: Asignación saltada, Recurso UID {res_uid_assign} no encontrado en mapa (probablemente no era WORK).")
                            # if target_task and target_task.required_resource_id is not None: print(f"Debug: Asignación saltada, Tarea UID {task_uid_assign} ya tenía recurso ID {target_task.required_resource_id}.")


                    except (ValueError, TypeError, AttributeError) as assign_e:
                        print(f"Adv (XmlReader): Error procesando asignación XML (TaskUID={task_uid_assign}, ResUID={res_uid_assign}): {assign_e}")
                        # traceback.print_exc()
                print(f"Info (XmlReader): {assignments_processed} asignaciones procesadas y aplicadas.")
            else:
                print("Advertencia: No se encontró la sección <Assignments> en el XML.")


            # --- 4. Procesar Dependencias (dentro de cada Tarea) ---
            print(f"Info (XmlReader): Procesando dependencias...")
            links_processed = 0
            if tasks_element is not None:
                for task_elem in tasks_element.findall(f'{{{ns}}}Task'):
                    succ_task_uid_elem = task_elem.find(f'{{{ns}}}UID')
                    if succ_task_uid_elem is None or succ_task_uid_elem.text is None: continue
                    succ_task_uid = int(succ_task_uid_elem.text)
                    succ_py_task = task_uid_map.get(succ_task_uid)
                    if not succ_py_task: continue # Tarea sucesora no encontrada o es resumen/raíz

                    # Buscar links predecesores dentro de esta tarea
                    for pred_link_elem in task_elem.findall(f'{{{ns}}}PredecessorLink'):
                        pred_uid_elem = None # Reset for error message clarity
                        try:
                            pred_uid_elem = pred_link_elem.find(f'{{{ns}}}PredecessorUID')
                            link_type_elem = pred_link_elem.find(f'{{{ns}}}Type')

                            if pred_uid_elem is None or link_type_elem is None: continue
                            # Skip if elements lack text content
                            if pred_uid_elem.text is None or link_type_elem.text is None: continue

                            link_type = int(link_type_elem.text)
                            # Procesar solo links Fin-a-Comienzo (FS)
                            if link_type == XML_TASK_LINK_TYPE_FS:
                                pred_task_uid = int(pred_uid_elem.text)
                                pred_py_task = task_uid_map.get(pred_task_uid)

                                if pred_py_task: # Si encontramos la tarea predecesora Python
                                    # Añadir dependencia si no existe ya
                                    if pred_py_task not in succ_py_task.dependencies:
                                        succ_py_task.dependencies.append(pred_py_task)
                                        links_processed += 1
                                # else: # Debug: Tarea predecesora no encontrada en el mapa
                                #     print(f"Adv: Tarea predecesora UID={pred_task_uid} para Tarea UID {succ_task_uid} no encontrada en el mapa de tareas válidas.")

                        except (ValueError, TypeError, AttributeError) as link_e:
                             pred_uid_text = pred_uid_elem.text if pred_uid_elem is not None else 'N/A'
                             print(f"Adv (XmlReader): Error procesando PredecessorLink para Tarea UID {succ_task_uid} (PredUID={pred_uid_text}): {link_e}")
                             # traceback.print_exc()
            print(f"Info (XmlReader): {links_processed} dependencias FS procesadas.")


            # --- 5. Finalizar y Calcular Baseline ---
            project.project_name = root.findtext(f'{{{ns}}}Name', default='Unnamed Project')
            project._calculate_baseline_metrics()
            print(f"Info (XmlReader): Carga completada desde XML. Proyecto '{project.project_name}'.")
            print(f"  Tareas: {len(project.tasks)}, Recursos: {len(project.resources)}, Costo Base Planificado: {project.baseline_cost:.2f}")

        except etree.XMLSyntaxError as xml_e:
            print(f"Error Crítico (XmlReader): Error de sintaxis XML en '{file_path}': {xml_e}")
            traceback.print_exc()
            raise ValueError(f"XmlReader: Archivo XML inválido: {xml_e}")
        except Exception as e:
            print(f"Error Crítico (XmlReader): Falló la carga o procesamiento del archivo XML '{file_path}': {e}")
            traceback.print_exc()
            raise ValueError(f"XmlReader: Falló al leer o procesar '{file_path}': {e}")

        return project