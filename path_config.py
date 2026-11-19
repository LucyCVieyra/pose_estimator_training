"""Carga y completa las rutas de entrenamiento desde training_paths.yaml."""

import json
import os
import re
from pathlib import Path
from typing import Dict


REQUIRED_PATHS = ("DATASET_ROOT", "LOGS_ROOT", "CSV_PATH")
CONFIG_PATH = Path(__file__).with_name("training_paths.yaml")


def _parse_scalar(value: str) -> str:
    """Interpreta escalares de ruta simples del esquema de este YAML."""
    value = value.strip()
    if not value:
        return ""
    if value.startswith("'"):
        if not value.endswith("'"):
            raise ValueError("Valor YAML entre comillas simples sin cerrar.")
        return value[1:-1].replace("''", "'")
    if value.startswith('"'):
        try:
            return str(json.loads(value))
        except json.JSONDecodeError as error:
            raise ValueError("Valor YAML entre comillas dobles no válido.") from error
    value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
    return "" if value.lower() in {"null", "~"} else value


def _read_paths(config_path: Path) -> Dict[str, str]:
    if not config_path.exists():
        return {}

    values: Dict[str, str] = {}
    in_training_paths = False
    with config_path.open("r", encoding="utf-8-sig") as config_file:
        for line in config_file:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if not line[0].isspace():
                in_training_paths = stripped == "training_paths:"
                continue
            if not in_training_paths:
                continue

            key, separator, raw_value = stripped.partition(":")
            if separator and key in REQUIRED_PATHS:
                values[key] = _parse_scalar(raw_value)
    return values


def _write_paths(config_path: Path, values: Dict[str, str]) -> None:
    lines = ["training_paths:"]
    for key in REQUIRED_PATHS:
        # Las comillas simples en YAML conservan las barras invertidas de Windows.
        escaped_value = values[key].replace("'", "''")
        lines.append(f"  {key}: '{escaped_value}'")
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_training_paths(config_path: Path = CONFIG_PATH) -> Dict[str, str]:
    """Lee las rutas y pregunta por los campos ausentes o vacíos.

    Las rutas relativas se interpretan desde la carpeta del YAML. Los valores
    solicitados se guardan en el archivo para las próximas ejecuciones.
    """
    values = _read_paths(config_path)
    updated = False

    for key in REQUIRED_PATHS:
        if not values.get(key, "").strip():
            while True:
                value = input(f"Ingresa la ruta para {key}: ").strip()
                if value:
                    values[key] = value
                    updated = True
                    break
                print("La ruta no puede quedar vacía.")

    if updated:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        _write_paths(config_path, values)
        print(f"Rutas guardadas en: {config_path}")

    resolved_paths = {}
    for key in REQUIRED_PATHS:
        expanded = os.path.expandvars(os.path.expanduser(values[key]))
        path = Path(expanded)
        if not path.is_absolute():
            path = config_path.parent / path
        resolved_paths[key] = str(path.resolve())
    return resolved_paths