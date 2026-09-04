"""Pruebas de impresión y sincronización offline."""
import uuid

import pytest


@pytest.fixture()
def setup(client, admin_headers):
    code = "P" + uuid.uuid4().hex[:6].upper()
    lab = client.post(
        "/api/v1/laboratories",
        headers=admin_headers,
        json={"country_code": "CO", "code": code, "name": "Lab Print"},
    ).json()["id"]
    tag = client.post(
        "/api/v1/equipment-tags",
        headers=admin_headers,
        json={"country_code": "CO", "laboratory_id": lab},
    ).json()
    size = client.get("/api/v1/label-sizes", headers=admin_headers).json()[0]["id"]
    return {"lab": lab, "tag": tag, "size": size}


def test_label_preview(client, admin_headers, setup):
    r = client.post(
        "/api/v1/labels/preview",
        headers=admin_headers,
        json={"equipment_id": setup["tag"]["id"], "label_size_id": setup["size"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["zpl"].startswith("^XA")
    assert setup["tag"]["serial_code"] in body["zpl"]


def test_print_and_reprint(client, admin_headers, setup):
    tid = setup["tag"]["id"]
    p = client.post(
        "/api/v1/labels/print",
        headers=admin_headers,
        json={"equipment_id": tid, "label_size_id": setup["size"], "copies": 2},
    )
    assert p.status_code == 200
    assert p.json()["print_job_id"]

    rp = client.post(
        f"/api/v1/equipment-tags/{tid}/reprint",
        headers=admin_headers,
        json={"equipment_id": tid, "label_size_id": setup["size"]},
    )
    assert rp.status_code == 200

    jobs = client.get(
        f"/api/v1/print-jobs?equipment_id={tid}", headers=admin_headers
    ).json()
    assert len(jobs) == 2
    assert any(j["is_reprint"] for j in jobs)


def test_sync_push_idempotent(client, admin_headers, setup):
    body = {
        "device_id": "tablet-test",
        "operations": [
            {
                "client_op_id": "sync-op-1",
                "type": "create",
                "payload": {"country_code": "CO", "laboratory_id": setup["lab"]},
            }
        ],
    }
    r1 = client.post("/api/v1/sync/push", headers=admin_headers, json=body).json()
    assert "sync-op-1" in r1["applied"]
    # Reenviar la misma operación no la duplica.
    r2 = client.post("/api/v1/sync/push", headers=admin_headers, json=body).json()
    assert "sync-op-1" in r2["applied"]


def test_sync_preserves_client_serial(client, admin_headers, setup):
    """Un serial definitivo generado offline se conserva al sincronizar."""
    serial = "OFFLINE7XYZ9K"
    body = {
        "device_id": "pc-panama",
        "operations": [
            {
                "client_op_id": "op-offline-1",
                "type": "create",
                "payload": {"country_code": "CO", "serial_code": serial},
            }
        ],
    }
    r = client.post("/api/v1/sync/push", headers=admin_headers, json=body).json()
    assert "op-offline-1" in r["applied"]
    created = {c["client_op_id"]: c for c in r["created"]}
    # El serial que sube el cliente es el mismo que queda en el servidor.
    assert created["op-offline-1"]["serial_code"] == serial

    # Otra PC que intente el MISMO serial (colisión) es rechazada, no duplicada.
    dup = {
        "device_id": "pc-otra",
        "operations": [
            {
                "client_op_id": "op-offline-2",
                "type": "create",
                "payload": {"country_code": "CO", "serial_code": serial},
            }
        ],
    }
    r2 = client.post("/api/v1/sync/push", headers=admin_headers, json=dup).json()
    assert "op-offline-2" not in r2["applied"]
    assert r2["rejected"] or r2["conflicts"]


def test_sync_pull(client, admin_headers):
    r = client.get("/api/v1/sync/pull", headers=admin_headers)
    assert r.status_code == 200
    assert "items" in r.json()
