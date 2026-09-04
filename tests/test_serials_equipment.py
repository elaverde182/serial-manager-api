"""Pruebas del núcleo: generación de seriales, ciclo de vida e historial."""
import uuid

import pytest


@pytest.fixture()
def lab_id(client, admin_headers):
    code = "T" + uuid.uuid4().hex[:6].upper()
    r = client.post(
        "/api/v1/laboratories",
        headers=admin_headers,
        json={"country_code": "CO", "code": code, "name": "Lab Test"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_generate_serial_format(client, admin_headers, lab_id):
    """Sin modelo (caso no esperado en la app): formato clásico PAÍS-CONSECUTIVO."""
    r = client.post(
        "/api/v1/equipment-tags",
        headers=admin_headers,
        json={"country_code": "CO", "laboratory_id": lab_id, "reason": "sin serial"},
    )
    assert r.status_code == 201, r.text
    tag = r.json()
    assert tag["serial_code"].startswith("CO-")
    assert tag["status"] == "active"
    assert len(tag["random_code"]) == 6


def test_serial_length_por_modelo(client, admin_headers):
    """Un modelo con serial_length genera un serial PLANO de esa longitud exacta."""
    r = client.post(
        "/api/v1/equipment-types",
        headers=admin_headers,
        json={"category": "CPE", "model": "TESTMODEL15", "serial_length": 15},
    )
    assert r.status_code == 201, r.text
    type_id = r.json()["id"]
    assert r.json()["serial_length"] == 15

    g = client.post(
        "/api/v1/equipment-tags",
        headers=admin_headers,
        json={"country_code": "CO", "equipment_type_id": type_id},
    )
    assert g.status_code == 201, g.text
    serial = g.json()["serial_code"]
    # Longitud exacta, sin prefijo de país ni separadores, y sin caracteres ambiguos.
    assert len(serial) == 15
    assert "-" not in serial
    assert not serial.startswith("CO-")
    assert set(serial) <= set("ABCDEFGHJKLMNPQRSTUVWXYZ23456789")


def test_consecutive_increments(client, admin_headers, lab_id):
    serials = []
    for _ in range(3):
        r = client.post(
            "/api/v1/equipment-tags",
            headers=admin_headers,
            json={"country_code": "CO", "laboratory_id": lab_id},
        )
        serials.append(r.json()["consecutive"])
    # Consecutivos estrictamente crecientes y sin repetir.
    assert len(set(serials)) == 3
    assert serials == sorted(serials)


def test_lifecycle_and_history(client, admin_headers, lab_id):
    tid = client.post(
        "/api/v1/equipment-tags",
        headers=admin_headers,
        json={"country_code": "CO", "laboratory_id": lab_id},
    ).json()["id"]

    client.post(f"/api/v1/equipment-tags/{tid}/inbound", headers=admin_headers, json={})
    d = client.post(
        f"/api/v1/equipment-tags/{tid}/discard",
        headers=admin_headers,
        json={"reason": "dañado"},
    )
    assert d.json()["status"] == "discarded"

    # No se puede descartar dos veces.
    d2 = client.post(
        f"/api/v1/equipment-tags/{tid}/discard",
        headers=admin_headers,
        json={"reason": "dañado"},
    )
    assert d2.status_code == 409

    events = [
        h["event"]
        for h in client.get(
            f"/api/v1/equipment-tags/{tid}/history", headers=admin_headers
        ).json()
    ]
    assert events == ["created", "inbound", "discarded"]


def test_idempotent_client_op_id(client, admin_headers, lab_id):
    body = {"country_code": "CO", "laboratory_id": lab_id, "client_op_id": "fixed-op-1"}
    a = client.post("/api/v1/equipment-tags", headers=admin_headers, json=body).json()
    b = client.post("/api/v1/equipment-tags", headers=admin_headers, json=body).json()
    assert a["id"] == b["id"]  # no se duplica


def test_filter_by_status(client, admin_headers, lab_id):
    r = client.get(
        "/api/v1/equipment-tags?status=discarded", headers=admin_headers
    ).json()
    assert all(i["status"] == "discarded" for i in r["items"])


def _operator_headers(client, admin_headers, username, country=None):
    body = {"username": username, "password": "op12345", "role_name": "operator"}
    if country:
        body["default_country_code"] = country
    client.post("/api/v1/users", headers=admin_headers, json=body)
    tok = client.post(
        "/api/v1/auth/login", json={"username": username, "password": "op12345"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def test_operator_locked_to_assigned_country(client, admin_headers):
    op = _operator_headers(client, admin_headers, "op_pais_co", country="CO")

    # Puede generar para su país asignado.
    r = client.post("/api/v1/equipment-tags", headers=op, json={"country_code": "CO"})
    assert r.status_code == 201, r.text

    # No puede generar para otro país (ni individual ni en lote).
    r = client.post("/api/v1/equipment-tags", headers=op, json={"country_code": "US"})
    assert r.status_code == 403
    r = client.post(
        "/api/v1/equipment-tags/batch",
        headers=op,
        json={"country_code": "US", "quantity": 2},
    )
    assert r.status_code == 403

    # Tampoco vía sync offline: la operación queda rechazada.
    r = client.post(
        "/api/v1/sync/push",
        headers=op,
        json={
            "device_id": "test-dev",
            "operations": [
                {"client_op_id": "op-pais-1", "type": "create", "payload": {"country_code": "US"}}
            ],
        },
    )
    assert r.status_code == 200
    assert r.json()["rejected"] and not r.json()["applied"]

    # El admin sí puede generar para cualquier país.
    r = client.post("/api/v1/equipment-tags", headers=admin_headers, json={"country_code": "US"})
    assert r.status_code == 201


def test_operator_without_country_cannot_generate(client, admin_headers):
    op = _operator_headers(client, admin_headers, "op_sin_pais")
    r = client.post("/api/v1/equipment-tags", headers=op, json={"country_code": "CO"})
    assert r.status_code == 403
