# core/readers/base_reader.py
from abc import ABC, abstractmethod
# Importar Project usando ruta absoluta desde core
from core.project import Project

class ProjectReader(ABC):
    """Interfaz abstracta para lectores de archivos de proyecto."""

    @abstractmethod
    def load(self, file_path: str) -> Project:
        """
        Carga datos de proyecto desde un archivo.

        Args:
            file_path: Ruta al archivo de proyecto.

        Returns:
            Una instancia de Project poblada con tareas, (opcionalmente) recursos,
            y dependencias.

        Raises:
            FileNotFoundError: Si el archivo no se encuentra.
            ValueError: Si el archivo no se puede leer o procesar.
            Exception: Otros errores inesperados.
        """
        pass