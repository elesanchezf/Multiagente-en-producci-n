"""Pruebas unitarias del directorio de empleados (solo lectura)."""

import pytest

from app.directory import DirectoryError, EmployeeDirectory


def test_known_employee_is_returned(directory):
    """Un identificador existente devuelve los datos del empleado."""
    employee = directory.get_employee("EMP-0004")
    assert employee["name"] == "Jorge Díaz"


def test_unknown_employee_is_reported(directory):
    """Un identificador inexistente devuelve None."""
    assert directory.get_employee("EMP-9999") is None


def test_department_search_lists_members_and_handles_no_match(directory):
    """La busqueda por departamento lista a sus miembros o devuelve una lista vacia."""
    names = {e["name"] for e in directory.search_by_department("Tecnología")}
    assert names == {"Ana López", "Jorge Díaz"}
    assert directory.search_by_department("Inexistente") == []


def test_missing_or_malformed_file_is_a_clear_error(tmp_path):
    """Un archivo ausente o con JSON invalido lanza DirectoryError."""
    with pytest.raises(DirectoryError):
        EmployeeDirectory.from_file(tmp_path / "missing.json")
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(DirectoryError):
        EmployeeDirectory.from_file(broken)
