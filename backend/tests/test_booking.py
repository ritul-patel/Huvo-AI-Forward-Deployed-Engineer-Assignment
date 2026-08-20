import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from main import app
import conversation

client = TestClient(app)

@patch("main.generate_agent_response")
def test_successful_site_visit(mock_generate):
    """6. SUCCESSFUL SITE VISIT"""
    mock_generate.return_value = "Booking Confirmed."
    session_id = "test_session_booking_success"
    
    response0 = client.post("/chat", json={"session_id": "", "message": "I want a 3 BHK."})
    real_session_id = response0.json()["session_id"]
    
    client.post("/chat", json={"session_id": real_session_id, "message": "My budget is 2 crore."})
    client.post("/chat", json={"session_id": real_session_id, "message": "I want to schedule a site visit."})
    response = client.post("/chat", json={"session_id": real_session_id, "message": "Saturday at 11 AM."})
    
    ctx = conversation.get_customer_context(real_session_id)
    
    assert ctx.site_visit_status == "confirmed"
    
    # Booking result should have NS- ID
    booking_res = conversation.get_booking_result(real_session_id)
    assert booking_res is not None
    assert booking_res.success is True
    assert booking_res.booking_id.startswith("NS-")

@patch("main.generate_agent_response")
def test_booking_failure(mock_generate):
    """7. BOOKING FAILURE"""
    mock_generate.return_value = "Booking Failed."
    session_id = "test_session_booking_failure"
    
    response0 = client.post("/chat", json={"session_id": "", "message": "I want to schedule a site visit."})
    real_session_id = response0.json()["session_id"]
    
    # Use an unresolvable date format to explicitly test failure
    response = client.post("/chat", json={"session_id": real_session_id, "message": "32/13/2099 at 11 AM."})
    
    ctx = conversation.get_customer_context(real_session_id)
    assert ctx.site_visit_status == "failed"
    
    booking_res = conversation.get_booking_result(real_session_id)
    assert booking_res is not None
    assert booking_res.success is False
    assert booking_res.booking_id is None

@patch("main.generate_agent_response")
def test_cancellation(mock_generate):
    """8. CANCELLATION"""
    mock_generate.return_value = "Cancelled."
    session_id = "test_session_booking_cancel"
    
    response0 = client.post("/chat", json={"session_id": "", "message": "I want to schedule a site visit."})
    real_session_id = response0.json()["session_id"]
    
    client.post("/chat", json={"session_id": real_session_id, "message": "Saturday at 11 AM."})
    
    ctx = conversation.get_customer_context(real_session_id)
    assert ctx.site_visit_status == "confirmed"
    
    # Send cancellation
    client.post("/chat", json={"session_id": real_session_id, "message": "Actually, don't book it. I'll decide later."})
    
    ctx = conversation.get_customer_context(real_session_id)
    assert ctx.site_visit_status == "cancelled"
    # Booking is not reported as confirmed in outcome (if we test analytics)
