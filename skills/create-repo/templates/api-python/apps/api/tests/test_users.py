def test_create_user(client):
    response = client.post("/users/", json={"name": "Alice", "email": "alice@example.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Alice"
    assert data["email"] == "alice@example.com"
    assert "id" in data


def test_list_users(client):
    client.post("/users/", json={"name": "Alice", "email": "alice@example.com"})
    client.post("/users/", json={"name": "Bob", "email": "bob@example.com"})
    response = client.get("/users/")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_user(client):
    create_resp = client.post("/users/", json={"name": "Alice", "email": "alice@example.com"})
    user_id = create_resp.json()["id"]
    response = client.get(f"/users/{user_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Alice"


def test_get_user_not_found(client):
    response = client.get("/users/999")
    assert response.status_code == 404


def test_update_user(client):
    create_resp = client.post("/users/", json={"name": "Alice", "email": "alice@example.com"})
    user_id = create_resp.json()["id"]
    response = client.patch(f"/users/{user_id}", json={"name": "Alice Updated"})
    assert response.status_code == 200
    assert response.json()["name"] == "Alice Updated"
    assert response.json()["email"] == "alice@example.com"


def test_delete_user(client):
    create_resp = client.post("/users/", json={"name": "Alice", "email": "alice@example.com"})
    user_id = create_resp.json()["id"]
    response = client.delete(f"/users/{user_id}")
    assert response.status_code == 200
    # Verify deleted
    response = client.get(f"/users/{user_id}")
    assert response.status_code == 404
