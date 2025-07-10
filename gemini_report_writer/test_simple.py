#!/usr/bin/env python3
import os
from dotenv import load_dotenv

# Load environment from parent directory
load_dotenv('../.env')

print("Testing environment variables...")
google_key = os.getenv('GOOGLE_API_KEY')
tavily_key = os.getenv('TAVILY_API_KEY')

print(f"GOOGLE_API_KEY: {'✓ Set' if google_key else '✗ Not set'}")
print(f"TAVILY_API_KEY: {'✓ Set' if tavily_key else '✗ Not set'}")

# Test basic imports
try:
    from utils import create_gemini_model
    print("✓ Utils import successful")
    
    # Test model creation
    model = create_gemini_model('planner')
    print("✓ Gemini model creation successful")
    
    # Test simple invoke
    response = model.invoke("What is quantum computing?")
    print(f"✓ Model response: {response.content[:100]}...")
    
except Exception as e:
    print(f"✗ Error: {e}")