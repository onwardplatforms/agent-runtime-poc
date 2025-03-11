import requests
import json
import time
import uuid
import os
from flask import Flask, request, jsonify
import openai
from dotenv import load_dotenv

app = Flask(__name__)

# Load environment variables from .env file
load_dotenv()

# Configuration
AGENT_ID = "hello-agent"  # Fixed ID to match the configuration
API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client
if not API_KEY:
    print("Error: OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
    exit(1)

# Create a client instance with the API key
client = openai.OpenAI(api_key=API_KEY)

@app.route('/api/message', methods=['POST'])
def receive_message():
    """Endpoint to receive messages"""
    message = request.json
    
    if not message:
        return jsonify({"error": "No message provided"}), 400
    
    # Process the message
    try:
        response_content = process_message(message)
        
        # Prepare response message
        response = {
            "messageId": str(uuid.uuid4()),
            "conversationId": message.get("conversationId", ""),
            "senderId": AGENT_ID,
            "recipientId": message.get("senderId", ""),
            "content": response_content,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "type": "Text"
        }
        
        # Return the response directly to the caller
        return jsonify(response), 200
    except Exception as e:
        print(f"Error processing message: {e}")
        return jsonify({"error": str(e)}), 500

def process_message(message):
    """Process the incoming message and generate a response"""
    content = message.get("content", "").lower()
    
    # Check if this is a greeting request
    if any(keyword in content for keyword in ["hello", "hi ", "greet", "bonjour", "hola"]):
        # Extract language if specified
        language = None
        if "french" in content:
            language = "French"
        elif "spanish" in content:
            language = "Spanish"
        elif "german" in content:
            language = "German"
        elif "italian" in content:
            language = "Italian"
        elif "japanese" in content:
            language = "Japanese"
        elif "chinese" in content:
            language = "Chinese"
        
        # Generate greeting
        return generate_greeting(language)
    
    # Default response for unrelated queries
    return "Hello Agent: I can help you with greetings. Try asking me to say hello in a specific language."

def generate_greeting(language=None):
    """Generate a greeting in the specified language or provide options"""
    try:
        prompt = "Generate a friendly greeting"
        
        if language:
            prompt += f" in {language}"
        else:
            prompt += " in English"
            
        # Using the newer OpenAI API format
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that generates friendly greetings."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=50
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating greeting: {e}")
        return f"Hello! (Sorry, I couldn't generate a greeting in {language if language else 'English'})"

if __name__ == "__main__":
    print("Starting Hello Agent with ID:", AGENT_ID)
    
    # Disable Flask access logs
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    # Run the Flask app
    app.run(host="0.0.0.0", port=5001) 