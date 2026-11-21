"""Directorio de empleados de solo lectura."""

import json
from pathlib import Path
from typing import Dict, List, Optional, Union


class DirectoryError(Exception):
    """Error al cargar o interpretar el archivo de empleados."""


class EmployeeDirectory:
    """Consulta de empleados en memoria, inmutable tras la carga.

    :param employees: Lista de empleados (diccionarios con campo ``id``).
    """

    def __init__(self, employees: List[Dict]):
        self._employees = tuple(dict(item) for item in employees)

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "EmployeeDirectory":
        """Carga el directorio desde un archivo JSON.

        :param path: Ruta del archivo.
        :return: El directorio cargado.
        :raises DirectoryError: Si el archivo falta o tiene formato inválido.
        """
        try:
            raw = Path(path).read_text(encoding="utf-8")
            data = json.loads(raw)
        except OSError as error:
            raise DirectoryError(f"Cannot read employees file: {path}") from error
        except json.JSONDecodeError as error:
            raise DirectoryError(f"Malformed employees file: {path}") from error
        valid = isinstance(data, list) and all(
            isinstance(item, dict) and "id" in item for item in data
        )
        if not valid:
            raise DirectoryError(f"Employees file must be a list of records: {path}")
        return cls(data)

    @property
    def departments(self) -> List[str]:
        """Nombres de departamento existentes, sin repetir.

        :return: Lista de departamentos en orden de aparición.
        """
        names = []
        for item in self._employees:
            name = item.get("department")
            if name and name not in names:
                names.append(name)
        return names

    def get_employee(self, employee_id: str) -> Optional[Dict]:
        """Busca un empleado por id.

        :param employee_id: Identificador, por ejemplo ``EMP-0004``.
        :return: Copia del registro o ``None`` si no existe.
        """
        for item in self._employees:
            if item["id"] == employee_id:
                return dict(item)
        return None

    def search_by_department(self, department: str) -> List[Dict]:
        """Lista los empleados de un departamento.

        :param department: Nombre del departamento (sin distinguir mayúsculas).
        :return: Lista de registros; vacía si no hay coincidencias.
        """
        wanted = str(department).strip().casefold()
        return [
            dict(item)
            for item in self._employees
            if str(item.get("department", "")).casefold() == wanted
        ]
