import pytest
import asyncio
from starlette.testclient import TestClient
from backend.app.main import app
from backend.app.database.schema import init_db
from backend.app.tools import init_all_tools

@pytest.fixture(autouse=True, scope="session")
def setup_test_environment():
    asyncio.run(init_db())
    init_all_tools()

client = TestClient(app)

def test_api_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["app"] == "NOVA"
    assert data["status"] == "online"
    assert data["port"] == 46815

def test_api_conversations_flow():
    # 1. Create conversation
    create_resp = client.post("/api/conversations", json={
        "title": "API Test Conversation",
        "permission_mode": "allow_safe"
    })
    assert create_resp.status_code == 200
    conv = create_resp.json()
    conv_id = conv["id"]

    # 2. List conversations
    list_resp = client.get("/api/conversations")
    assert list_resp.status_code == 200
    convs = list_resp.json()
    assert any(c["id"] == conv_id for c in convs)

    # 3. Get single conversation
    get_resp = client.get(f"/api/conversations/{conv_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["conversation"]["id"] == conv_id

    # 4. Patch title
    patch_resp = client.patch(f"/api/conversations/{conv_id}", json={"title": "Renamed API Conv"})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "Renamed API Conv"

    # 5. Delete conversation
    del_resp = client.delete(f"/api/conversations/{conv_id}")
    assert del_resp.status_code == 200

def test_api_tools_endpoint():
    resp = client.get("/api/tools")
    assert resp.status_code == 200
    tools = resp.json()
    assert len(tools) >= 20
    tool_names = [t["name"] for t in tools]
    assert "execute_powershell" in tool_names
    assert "get_system_information" in tool_names
    assert "list_directory" in tool_names

def test_api_agent_profiles():
    resp = client.get("/api/agent-profiles")
    assert resp.status_code == 200
    profiles = resp.json()
    assert len(profiles) >= 5

def test_api_settings_and_db_status():
    s_resp = client.get("/api/settings")
    assert s_resp.status_code == 200
    assert "general" in s_resp.json()

    db_resp = client.get("/api/database/status")
    assert db_resp.status_code == 200
    assert "conversations_count" in db_resp.json()
