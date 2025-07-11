import os
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

# Centralized mapping of agent roles to Gemini model names
AGENT_MODEL_MAPPING = {
    "planner": "gemini-2.5-flash",
    "critic": "gemini-2.5-flash",
    "researcher": "gemini-2.5-flash-lite-preview-06-17",
    "writer": "gemini-2.5-flash-lite-preview-06-17",
    "citation_verifier": "gemini-2.5-flash-lite-preview-06-17",
    "retriever": "gemini-2.5-flash",
    "apa_formatter": "gemini-2.5-flash-lite-preview-06-17",
    "content_verifier": "gemini-2.5-flash",
    "quality_controller": "gemini-2.5-flash",
}

def create_gemini_model(agent_role: str, temperature: float = 0):
    """Creates a Gemini model instance based on the agent's role."""
    model_name = AGENT_MODEL_MAPPING.get(agent_role)
    if not model_name:
        raise ValueError(f"No model specified for agent role: {agent_role}")

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set!")
    return ChatGoogleGenerativeAI(model=model_name, temperature=temperature, google_api_key=api_key)