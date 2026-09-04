"""Pruebas de autenticación, RBAC y usuarios."""


def test_health(client):
    assert client.get("/health").status_code == 200
    assert client.get("/health/db").json()["database"] == "up"


def test_login_ok_and_me(client, admin_headers):
    me = client.get("/api/v1/auth/me", headers=admin_headers).json()
    assert me["username"] == "admin"
    assert me["role"] == "admin"


def test_login_bad_credentials(client):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "x"})
    assert r.status_code == 401


def test_unauthenticated_is_rejected(client):
    assert client.get("/api/v1/users").status_code == 401


def test_operator_cannot_list_users(client, admin_headers):
    client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"username": "op_rbac", "password": "op12345", "role_name": "operator"},
    )
    tok = client.post(
        "/api/v1/auth/login", json={"username": "op_rbac", "password": "op12345"}
    ).json()["access_token"]
    r = client.get("/api/v1/users", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403


def test_operator_cannot_change_own_country(client, admin_headers):
    client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"username": "op_country", "password": "op12345", "role_name": "operator"},
    )
    tok = client.post(
        "/api/v1/auth/login", json={"username": "op_country", "password": "op12345"}
    ).json()["access_token"]
    op_headers = {"Authorization": f"Bearer {tok}"}

    # El operador NO puede cambiar su país por defecto.
    r = client.patch("/api/v1/auth/me", headers=op_headers, json={"default_country_code": "CO"})
    assert r.status_code == 403

    # Pero sí puede cambiar su idioma (autoservicio).
    r = client.patch("/api/v1/auth/me", headers=op_headers, json={"language": "en"})
    assert r.status_code == 200
    assert r.json()["language"] == "en"

    # El admin sí puede cambiar su propio país.
    r = client.patch("/api/v1/auth/me", headers=admin_headers, json={"default_country_code": "CO"})
    assert r.status_code == 200
    assert r.json()["default_country_code"] == "CO"


def test_supervisor_manages_models_only(client, admin_headers):
    """El supervisor puede crear/editar modelos, pero no otros catálogos ni usuarios."""
    client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"username": "sup1", "password": "sup12345", "role_name": "supervisor"},
    )
    tok = client.post(
        "/api/v1/auth/login", json={"username": "sup1", "password": "sup12345"}
    ).json()["access_token"]
    sup = {"Authorization": f"Bearer {tok}"}

    # Puede crear un modelo con su longitud de serial.
    r = client.post(
        "/api/v1/equipment-types",
        headers=sup,
        json={"category": "CPE", "model": "SUPMODEL1", "serial_length": 13},
    )
    assert r.status_code == 201, r.text
    type_id = r.json()["id"]

    # Puede editarlo.
    r = client.patch(
        f"/api/v1/equipment-types/{type_id}", headers=sup, json={"serial_length": 14}
    )
    assert r.status_code == 200 and r.json()["serial_length"] == 14

    # NO puede tocar otros catálogos (países) ni usuarios.
    assert (
        client.post(
            "/api/v1/countries", headers=sup,
            json={"code": "ZZ", "name": "Z", "prefix": "ZZ"},
        ).status_code
        == 403
    )
    assert client.get("/api/v1/users", headers=sup).status_code == 403


def test_refresh_token(client):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    refresh = r.json()["refresh_token"]
    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r2.status_code == 200
    assert r2.json()["access_token"]
