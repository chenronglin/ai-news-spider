FIXTURE_URL_1 = "https://example.com/list.htm"
FIXTURE_URL_2 = "https://example.com/list/1.htm"
FIXTURE_URL_3 = "https://example.com/list/2.htm"


def build_auth_headers(token: str) -> dict[str, str]:
    return {"X-API-Token": token}


def wait_for_task_completion(
    client,
    task_id: int,
    *,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = 5.0,
):
    import time

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get(f"/api/v1/tasks/{task_id}", headers=headers)
        response.raise_for_status()
        payload = response.json()
        if payload["status"] in {"succeeded", "failed", "cancelled"}:
            return payload
        time.sleep(0.05)
    raise AssertionError(
        f"task {task_id} did not finish within {timeout_seconds} seconds"
    )
