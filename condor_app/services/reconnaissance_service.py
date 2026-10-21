"""Curated fictional migration artifacts for the terminal reconnaissance exercise.

These intentionally exposed records model a forgotten backup, not real personnel.
They contain no password, hash, secret key, flag, or direct solution field. A learner
must correlate profiles with each account's most recent state transition.
"""

import csv
import io


def manifest(artifact_urls):
    return {
        "formato": "condor-migracion/v1",
        "descripcion": "Respaldo de migración del portal de personal. Datos ficticios de entrenamiento.",
        "archivos": dict(artifact_urls),
        "relacion": "cuentas.id corresponde a bitacora.eventos.cuenta_id",
        "regla_publicacion": {
            "perfil_requerido": "editor",
            "estado_requerido": "activo",
            "criterio_estado": "El estado vigente es el evento con mayor secuencia de cada cuenta_id.",
        },
        "nota": "El respaldo conserva perfiles anteriores. No todos los registros corresponden a cuentas vigentes.",
    }


def accounts_csv(admin_username):
    # The only real account is supplied by app configuration. Other names are decoys.
    def decoy(name):
        return name if name != admin_username else name + ".archivo"

    records = [
        ("CD-104", decoy("operador.sierra"), "consulta", "logistica"),
        ("CD-208", decoy("editor.pacifico"), "editor", "comunicaciones"),
        ("CD-319", admin_username, "editor", "comunicaciones"),
        ("CD-427", decoy("admin.general"), "editor", "archivo"),
        ("CD-506", decoy("enlace.austro"), "auditor", "coordinacion"),
    ]
    content = io.StringIO(newline="")
    writer = csv.writer(content, lineterminator="\n")
    writer.writerow(("id", "usuario", "perfil", "area"))
    writer.writerows(records)
    return content.getvalue()


def audit_log():
    # Deliberately not sorted: the last line is not necessarily the newest event.
    transitions = [
        (7, "CD-319", "activo", "2026-10-01T11:30:00Z"),
        (2, "CD-208", "activo", "2026-09-01T08:20:00Z"),
        (5, "CD-506", "activo", "2026-09-02T09:00:00Z"),
        (1, "CD-104", "activo", "2026-09-01T08:00:00Z"),
        (6, "CD-208", "inactivo", "2026-09-20T10:00:00Z"),
        (3, "CD-319", "pendiente", "2026-09-01T08:40:00Z"),
        (8, "CD-427", "retirado", "2026-10-02T16:00:00Z"),
        (4, "CD-427", "activo", "2026-09-01T09:00:00Z"),
    ]
    return {
        "formato": "condor-estados/v1",
        "eventos": [
            {"secuencia": sequence, "cuenta_id": account_id, "estado": state, "fecha": at}
            for sequence, account_id, state, at in transitions
        ],
    }
