def test_send_reply_endpoint(client) -> None:
    response = client.post(
        "/api/demo/vertice360-ai-workflow/send-reply",
        json={"ticketId": "VTX-0001", "to": "5491130000000", "text": "Hola"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("ok") is True
