import pytest
from conversation import create_session, get_customer_context, update_customer_context, get_messages

def test_conversation_memory():
    """2. CONVERSATION MEMORY"""
    session_id = create_session()
    
    # Turn 1
    update_customer_context(session_id, {"configuration": "2 BHK"})
    ctx1 = get_customer_context(session_id)
    assert ctx1.configuration == "2 BHK"
    
    # Turn 2
    update_customer_context(session_id, {"configuration": "3 BHK"})
    ctx2 = get_customer_context(session_id)
    assert ctx2.configuration == "3 BHK"
