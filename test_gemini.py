#!/usr/bin/env python3
"""Quick Gemini API test script"""

import os
import sys
sys.path.append('/home/samarth/Hackathons/hackbyte_4.0/DreamOps/backend/src')

try:
    import google.generativeai as genai
    
    # Test API key
    api_key = "AIzaSyDIAKbZSudes3ivzdQQOXrsFPk9249Ptuc"
    genai.configure(api_key=api_key)
    
    # Test model
    model = genai.GenerativeModel('gemini-pro')
    
    prompt = """
Analyze this incident: Kubernetes pod payment-service experiencing OOM errors.
Provide:
1. Root cause
2. Immediate actions  
3. Recommendations

Keep response concise (max 200 words).
"""
    
    response = model.generate_content(prompt)
    print("✅ Gemini API Test Successful!")
    print("Response preview:", response.text[:200] + "...")
    
except Exception as e:
    print(f"❌ Gemini API Test Failed: {e}")