import json
import time
import uuid
import os
import re
import math
from flask import Flask, request, jsonify, Response, stream_with_context
import openai
from dotenv import load_dotenv

app = Flask(__name__)

# Load environment variables from .env file
load_dotenv()

# Configuration
AGENT_ID = "math-agent"  # Fixed ID to match the configuration
API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client
if not API_KEY:
    print("Error: OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
    exit(1)

# Create a client instance with the API key
client = openai.OpenAI(api_key=API_KEY)

# Math operations
def add(a, b):
    """Add two numbers together."""
    try:
        return float(a) + float(b)
    except ValueError:
        return "Error: Please provide valid numbers."

def subtract(a, b):
    """Subtract the second number from the first."""
    try:
        return float(a) - float(b)
    except ValueError:
        return "Error: Please provide valid numbers."

def multiply(a, b):
    """Multiply two numbers together."""
    try:
        return float(a) * float(b)
    except ValueError:
        return "Error: Please provide valid numbers."

def divide(a, b):
    """Divide the first number by the second."""
    try:
        if float(b) == 0:
            return "Error: Cannot divide by zero."
        return float(a) / float(b)
    except ValueError:
        return "Error: Please provide valid numbers."

def square_root(a):
    """Calculate the square root of a number."""
    try:
        if float(a) < 0:
            return "Error: Cannot calculate square root of a negative number."
        return math.sqrt(float(a))
    except ValueError:
        return "Error: Please provide a valid number."

def power(a, b):
    """Raise the first number to the power of the second."""
    try:
        return float(a) ** float(b)
    except ValueError:
        return "Error: Please provide valid numbers."

def percentage(a, b):
    """Calculate what percentage the first number is of the second."""
    try:
        if float(b) == 0:
            return "Error: Cannot calculate percentage with zero as the whole."
        return (float(a) / float(b)) * 100
    except ValueError:
        return "Error: Please provide valid numbers."

# Function to parse math operations from text
def parse_math_operation(text):
    """Parse a math operation from text."""
    # Addition
    add_match = re.search(r'(\d+\.?\d*)\s*\+\s*(\d+\.?\d*)', text)
    if add_match:
        a, b = add_match.groups()
        result = add(a, b)
        return f"{a} + {b} = {result}"
    
    # Subtraction
    sub_match = re.search(r'(\d+\.?\d*)\s*\-\s*(\d+\.?\d*)', text)
    if sub_match:
        a, b = sub_match.groups()
        result = subtract(a, b)
        return f"{a} - {b} = {result}"
    
    # Multiplication
    mul_match = re.search(r'(\d+\.?\d*)\s*\*\s*(\d+\.?\d*)', text) or re.search(r'(\d+\.?\d*)\s*x\s*(\d+\.?\d*)', text, re.IGNORECASE)
    if mul_match:
        a, b = mul_match.groups()
        result = multiply(a, b)
        return f"{a} × {b} = {result}"
    
    # Division
    div_match = re.search(r'(\d+\.?\d*)\s*\/\s*(\d+\.?\d*)', text) or re.search(r'(\d+\.?\d*)\s*÷\s*(\d+\.?\d*)', text)
    if div_match:
        a, b = div_match.groups()
        result = divide(a, b)
        return f"{a} ÷ {b} = {result}"
    
    # Square root
    sqrt_match = re.search(r'square\s*root\s*of\s*(\d+\.?\d*)', text, re.IGNORECASE) or re.search(r'sqrt\s*\(?(\d+\.?\d*)\)?', text, re.IGNORECASE)
    if sqrt_match:
        a = sqrt_match.group(1)
        result = square_root(a)
        return f"√{a} = {result}"
    
    # Power
    pow_match = re.search(r'(\d+\.?\d*)\s*\^\s*(\d+\.?\d*)', text) or re.search(r'(\d+\.?\d*)\s*to the power of\s*(\d+\.?\d*)', text, re.IGNORECASE)
    if pow_match:
        a, b = pow_match.groups()
        result = power(a, b)
        return f"{a}^{b} = {result}"
    
    # Percentage
    pct_match = re.search(r'what\s*percentage\s*is\s*(\d+\.?\d*)\s*of\s*(\d+\.?\d*)', text, re.IGNORECASE) or re.search(r'(\d+\.?\d*)\s*percent\s*of\s*(\d+\.?\d*)', text, re.IGNORECASE)
    if pct_match:
        a, b = pct_match.groups()
        result = percentage(a, b)
        return f"{a} is {result}% of {b}"
    
    # Natural language parsing with OpenAI
    return None

@app.route('/api/message', methods=['POST'])
def receive_message():
    """Endpoint to receive messages"""
    message = request.json
    
    if not message:
        return jsonify({"error": "No message provided"}), 400
    
    # Check if streaming is requested
    stream = message.get("stream", False)
    
    if stream:
        return Response(
            stream_with_context(process_message_stream(message)),
            content_type='text/event-stream'
        )
    else:
        # Process the message synchronously
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

def stream_with_context(generator):
    """Stream the response with proper SSE formatting."""
    try:
        for chunk in generator:
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        print(f"Error in streaming: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"

def process_message_stream(message):
    """Process the message and stream the response."""
    content = message.get("content", "")
    conversation_id = message.get("conversationId", "")
    sender_id = message.get("senderId", "")
    
    # Create a unique message ID for this response
    message_id = str(uuid.uuid4())
    
    # Yield initial chunk to establish the connection
    yield {
        "messageId": message_id,
        "conversationId": conversation_id,
        "senderId": AGENT_ID,
        "recipientId": sender_id,
        "content": "",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "type": "Text",
        "chunk": "Starting math calculation...",
        "complete": False
    }
    
    try:
        # Try to parse the math operation directly
        result = parse_math_operation(content)
        
        # If direct parsing failed, use OpenAI to interpret the query
        if result is None:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a math assistant. Extract the mathematical operation from the user's query and express it in a simple format like '5 + 3' or 'square root of 16'. Only respond with the mathematical expression, nothing else."},
                    {"role": "user", "content": content}
                ],
                max_tokens=50
            )
            
            # Extract the mathematical expression
            math_expression = response.choices[0].message.content.strip()
            
            # Try to parse the extracted expression
            result = parse_math_operation(math_expression)
            
            # If still no result, use OpenAI to solve it
            if result is None:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a math assistant. Solve the mathematical problem and show your work step by step."},
                        {"role": "user", "content": content}
                    ],
                    max_tokens=150
                )
                
                result = response.choices[0].message.content.strip()
        
        # Stream the response content character by character for demonstration
        buffer = ""
        for char in result:
            buffer += char
            if len(buffer) >= 5 or char in ['.', ',', '!', '?', ' ', '\n']:
                yield {
                    "messageId": message_id,
                    "conversationId": conversation_id,
                    "senderId": AGENT_ID,
                    "recipientId": sender_id,
                    "content": buffer,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "type": "Text",
                    "chunk": buffer,
                    "complete": False
                }
                buffer = ""
                time.sleep(0.01)  # Small delay for demonstration
        
        # Send any remaining buffer
        if buffer:
            yield {
                "messageId": message_id,
                "conversationId": conversation_id,
                "senderId": AGENT_ID,
                "recipientId": sender_id,
                "content": buffer,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "type": "Text",
                "chunk": buffer,
                "complete": False
            }
        
        # Final chunk to indicate completion
        yield {
            "messageId": message_id,
            "conversationId": conversation_id,
            "senderId": AGENT_ID,
            "recipientId": sender_id,
            "content": result,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "type": "Text",
            "chunk": None,
            "complete": True
        }
    except Exception as e:
        print(f"Error in streaming process: {e}")
        yield {
            "messageId": message_id,
            "conversationId": conversation_id,
            "senderId": AGENT_ID,
            "recipientId": sender_id,
            "content": f"Error: {str(e)}",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "type": "Text",
            "chunk": f"Error: {str(e)}",
            "complete": True
        }

def process_message(message):
    """Process the incoming message and generate a response"""
    content = message.get("content", "")
    
    # Try to parse the math operation directly
    result = parse_math_operation(content)
    
    # If direct parsing failed, use OpenAI to interpret the query
    if result is None:
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a math assistant. Extract the mathematical operation from the user's query and express it in a simple format like '5 + 3' or 'square root of 16'. Only respond with the mathematical expression, nothing else."},
                    {"role": "user", "content": content}
                ],
                max_tokens=50
            )
            
            # Extract the mathematical expression
            math_expression = response.choices[0].message.content.strip()
            
            # Try to parse the extracted expression
            result = parse_math_operation(math_expression)
            
            # If still no result, use OpenAI to solve it
            if result is None:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a math assistant. Solve the mathematical problem and show your work step by step."},
                        {"role": "user", "content": content}
                    ],
                    max_tokens=150
                )
                
                result = response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error using OpenAI: {e}")
            result = f"I encountered an error while processing your math query: {str(e)}"
    
    return result

if __name__ == "__main__":
    print("Starting Math Agent with ID:", AGENT_ID)
    
    # Disable Flask access logs
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    # Run the Flask app
    app.run(host="0.0.0.0", port=5004) 