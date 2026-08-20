import pytest
from intent import extract_intents, extract_entities

def test_basic_qualification():
    """1. BASIC QUALIFICATION"""
    msg = "I am looking for a 3 BHK with a budget of 2 crore."
    entities = extract_entities(msg)
    assert entities.configuration == "3 BHK"
    assert entities.budget == "2 crore"

def test_hinglish():
    """4. HINGLISH"""
    msg = "Mujhe 3 BHK chahiye, budget 2 crore hai."
    entities = extract_entities(msg)
    assert entities.configuration == "3 BHK"
    assert entities.budget == "2 crore"
    assert entities.language == "Hinglish"

def test_follow_up_request():
    """9. FOLLOW-UP REQUEST"""
    msg = "I'm busy right now. Call me next week."
    intents = extract_intents(msg)
    assert intents.follow_up_request is True
    assert intents.busy is True

def test_stop_communication():
    """10. STOP COMMUNICATION"""
    msg = "Don't contact me again."
    intents = extract_intents(msg)
    assert intents.stop_communication is True
