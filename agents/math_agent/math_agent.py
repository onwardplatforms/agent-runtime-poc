import json
import time
import uuid
import os
import re
import math
from flask import Flask, request, jsonify, Response, stream_with_context
import openai
from dotenv import load_dotenv

from reasoning import ReasoningChain, MessageType

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

# Math operations with reasoning
def add(a, b, chain=None):
    """Add two numbers together with reasoning."""
    try:
        a_float = float(a)
        b_float = float(b)
        result = a_float + b_float
        
        if chain:
            chain.add_reasoning(f"I need to add {a} and {b} together.")
            chain.add_calculation("add", {"a": a, "b": b}, result)
        
        return result
    except ValueError:
        error_msg = "Error: Please provide valid numbers."
        if chain:
            chain.add_reasoning(f"I encountered an error: {error_msg}")
        return error_msg

def subtract(a, b, chain=None):
    """Subtract the second number from the first with reasoning."""
    try:
        a_float = float(a)
        b_float = float(b)
        result = a_float - b_float
        
        if chain:
            chain.add_reasoning(f"I need to subtract {b} from {a}.")
            chain.add_calculation("subtract", {"a": a, "b": b}, result)
        
        return result
    except ValueError:
        error_msg = "Error: Please provide valid numbers."
        if chain:
            chain.add_reasoning(f"I encountered an error: {error_msg}")
        return error_msg

def multiply(a, b, chain=None):
    """Multiply two numbers together with reasoning."""
    try:
        a_float = float(a)
        b_float = float(b)
        result = a_float * b_float
        
        if chain:
            chain.add_reasoning(f"I need to multiply {a} by {b}.")
            chain.add_calculation("multiply", {"a": a, "b": b}, result)
        
        return result
    except ValueError:
        error_msg = "Error: Please provide valid numbers."
        if chain:
            chain.add_reasoning(f"I encountered an error: {error_msg}")
        return error_msg

def divide(a, b, chain=None):
    """Divide the first number by the second with reasoning."""
    try:
        a_float = float(a)
        b_float = float(b)
        
        if b_float == 0:
            error_msg = "Error: Cannot divide by zero."
            if chain:
                chain.add_reasoning(f"I encountered an error: {error_msg}")
            return error_msg
        
        result = a_float / b_float
        
        if chain:
            chain.add_reasoning(f"I need to divide {a} by {b}.")
            chain.add_calculation("divide", {"a": a, "b": b}, result)
        
        return result
    except ValueError:
        error_msg = "Error: Please provide valid numbers."
        if chain:
            chain.add_reasoning(f"I encountered an error: {error_msg}")
        return error_msg

def square_root(a, chain=None):
    """Calculate the square root of a number with reasoning."""
    try:
        a_float = float(a)
        
        if a_float < 0:
            error_msg = "Error: Cannot calculate square root of a negative number."
            if chain:
                chain.add_reasoning(f"I encountered an error: {error_msg}")
            return error_msg
        
        result = math.sqrt(a_float)
        
        if chain:
            chain.add_reasoning(f"I need to find the square root of {a}.")
            chain.add_calculation("square_root", {"a": a}, result)
        
        return result
    except ValueError:
        error_msg = "Error: Please provide a valid number."
        if chain:
            chain.add_reasoning(f"I encountered an error: {error_msg}")
        return error_msg

def power(a, b, chain=None):
    """Raise the first number to the power of the second with reasoning."""
    try:
        a_float = float(a)
        b_float = float(b)
        result = a_float ** b_float
        
        if chain:
            chain.add_reasoning(f"I need to raise {a} to the power of {b}.")
            chain.add_calculation("power", {"a": a, "b": b}, result)
        
        return result
    except ValueError:
        error_msg = "Error: Please provide valid numbers."
        if chain:
            chain.add_reasoning(f"I encountered an error: {error_msg}")
        return error_msg

def percentage(a, b, chain=None):
    """Calculate what percentage the first number is of the second with reasoning."""
    try:
        a_float = float(a)
        b_float = float(b)
        
        if b_float == 0:
            error_msg = "Error: Cannot calculate percentage with zero as the whole."
            if chain:
                chain.add_reasoning(f"I encountered an error: {error_msg}")
            return error_msg
        
        result = (a_float / b_float) * 100
        
        if chain:
            chain.add_reasoning(f"I need to find what percentage {a} is of {b}.")
            chain.add_calculation("percentage", {"a": a, "b": b}, result)
        
        return result
    except ValueError:
        error_msg = "Error: Please provide valid numbers."
        if chain:
            chain.add_reasoning(f"I encountered an error: {error_msg}")
        return error_msg

# Function to parse math operations from text with reasoning
def parse_math_operation(text, with_reasoning=False):
    """Parse a math operation from text with optional reasoning."""
    chain = ReasoningChain() if with_reasoning else None
    
    if chain:
        chain.add_reasoning(f"Analyzing the query: '{text}'")
    
    # Addition
    add_match = re.search(r'(\d+\.?\d*)\s*\+\s*(\d+\.?\d*)', text)
    if add_match:
        a, b = add_match.groups()
        if chain:
            chain.add_reasoning(f"I identified an addition operation: {a} + {b}")
        result = add(a, b, chain)
        
        if chain:
            chain.add_response(f"{a} + {b} = {result}")
            return chain.get_detailed_explanation()
        return f"{a} + {b} = {result}"
    
    # Subtraction
    sub_match = re.search(r'(\d+\.?\d*)\s*\-\s*(\d+\.?\d*)', text)
    if sub_match:
        a, b = sub_match.groups()
        if chain:
            chain.add_reasoning(f"I identified a subtraction operation: {a} - {b}")
        result = subtract(a, b, chain)
        
        if chain:
            chain.add_response(f"{a} - {b} = {result}")
            return chain.get_detailed_explanation()
        return f"{a} - {b} = {result}"
    
    # Multiplication
    mul_match = re.search(r'(\d+\.?\d*)\s*\*\s*(\d+\.?\d*)', text) or re.search(r'(\d+\.?\d*)\s*x\s*(\d+\.?\d*)', text, re.IGNORECASE)
    if mul_match:
        a, b = mul_match.groups()
        if chain:
            chain.add_reasoning(f"I identified a multiplication operation: {a} × {b}")
        result = multiply(a, b, chain)
        
        if chain:
            chain.add_response(f"{a} × {b} = {result}")
            return chain.get_detailed_explanation()
        return f"{a} × {b} = {result}"
    
    # Division
    div_match = re.search(r'(\d+\.?\d*)\s*\/\s*(\d+\.?\d*)', text) or re.search(r'(\d+\.?\d*)\s*÷\s*(\d+\.?\d*)', text)
    if div_match:
        a, b = div_match.groups()
        if chain:
            chain.add_reasoning(f"I identified a division operation: {a} ÷ {b}")
        result = divide(a, b, chain)
        
        if chain:
            chain.add_response(f"{a} ÷ {b} = {result}")
            return chain.get_detailed_explanation()
        return f"{a} ÷ {b} = {result}"
    
    # Square root
    sqrt_match = re.search(r'square\s*root\s*of\s*(\d+\.?\d*)', text, re.IGNORECASE) or re.search(r'sqrt\s*\(?(\d+\.?\d*)\)?', text, re.IGNORECASE)
    if sqrt_match:
        a = sqrt_match.group(1)
        if chain:
            chain.add_reasoning(f"I identified a square root operation: √{a}")
        result = square_root(a, chain)
        
        if chain:
            chain.add_response(f"√{a} = {result}")
            return chain.get_detailed_explanation()
        return f"√{a} = {result}"
    
    # Power
    pow_match = re.search(r'(\d+\.?\d*)\s*\^\s*(\d+\.?\d*)', text) or re.search(r'(\d+\.?\d*)\s*to the power of\s*(\d+\.?\d*)', text, re.IGNORECASE)
    if pow_match:
        a, b = pow_match.groups()
        if chain:
            chain.add_reasoning(f"I identified a power operation: {a}^{b}")
        result = power(a, b, chain)
        
        if chain:
            chain.add_response(f"{a}^{b} = {result}")
            return chain.get_detailed_explanation()
        return f"{a}^{b} = {result}"
    
    # Percentage
    pct_match = re.search(r'what\s*percentage\s*is\s*(\d+\.?\d*)\s*of\s*(\d+\.?\d*)', text, re.IGNORECASE) or \
                re.search(r'(\d+\.?\d*)\s*percent\s*of\s*(\d+\.?\d*)', text, re.IGNORECASE) or \
                re.search(r'(\d+\.?\d*)%\s*of\s*(\d+\.?\d*)', text, re.IGNORECASE)
    if pct_match:
        a, b = pct_match.groups()
        if chain:
            chain.add_reasoning(f"I identified a percentage operation: {a}% of {b}")
        
        # In "X% of Y", we want to calculate X% * Y, not what percentage X is of Y
        if "percent of" in text.lower() or "% of" in text:
            result = float(a) * float(b) / 100
            if chain:
                chain.add_calculation("percentage_of", {"percentage": a, "value": b}, result)
                chain.add_response(f"{a}% of {b} = {result}")
                return chain.get_detailed_explanation()
            return f"{a}% of {b} = {result}"
        else:
            result = percentage(a, b, chain)
            if chain:
                chain.add_response(f"{a} is {result}% of {b}")
                return chain.get_detailed_explanation()
            return f"{a} is {result}% of {b}"
    
    # Natural language parsing with OpenAI
    if chain:
        chain.add_reasoning("I couldn't identify a direct mathematical operation in the query. I'll use OpenAI to help interpret it.")
    
    return None

def handle_complex_problem(text, chain=None):
    """
    Handle complex mathematical problems by breaking them down into steps.
    Uses the reasoning chain to document the step-by-step problem-solving process.
    """
    if chain:
        chain.add_reasoning(f"Analyzing the query: '{text}'")
        chain.add_reasoning("I'll break this down into steps to solve it methodically.")
    
    # Use OpenAI to help break down the problem
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": """You are a mathematical reasoning assistant that breaks down complex problems into steps.
                Identify the type of problem, explain the approach, and provide step-by-step instructions for solving it.
                Don't actually solve the problem - just explain HOW to solve it with clear, discrete steps.
                Focus on using basic operations: addition, subtraction, multiplication, division, percentages, powers, and square roots."""},
                {"role": "user", "content": f"Break down how to solve this math problem step by step: {text}"}
            ],
            max_tokens=300
        )
        
        breakdown = response.choices[0].message.content.strip()
        
        if chain:
            chain.add_reasoning("Problem breakdown plan:")
            chain.add_reasoning(breakdown)
        
        # Now execute the plan using basic operations
        final_result = execute_math_plan(text, breakdown, chain)
        return final_result
        
    except Exception as e:
        error_msg = f"Error breaking down the problem: {str(e)}"
        if chain:
            chain.add_reasoning(error_msg)
        return error_msg

def execute_math_plan(original_query, breakdown, chain=None):
    """
    Execute a mathematical plan derived from the breakdown of a complex problem.
    """
    if chain:
        chain.add_reasoning("Now I'll execute this plan using my basic math operations.")
    
    try:
        # Use OpenAI to actually solve the problem step by step
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": """You are a mathematical reasoning assistant that solves problems step by step.
                Follow the breakdown plan and show each calculation with clear intermediate results.
                Express all formulas and calculations explicitly.
                For compound interest, show the complete formula: A = P(1 + r/n)^(nt) and calculate each step.
                Always show your work and explain each operation."""},
                {"role": "user", "content": f"Original problem: {original_query}\n\nSolution plan: {breakdown}\n\nSolve this step by step, showing all calculations clearly."}
            ],
            max_tokens=500
        )
        
        solution = response.choices[0].message.content.strip()
        
        if chain:
            # Extract key steps and add them to reasoning
            solution_lines = solution.split('\n')
            for line in solution_lines:
                if line.strip():
                    chain.add_reasoning(line)
            
            # Try to extract the final answer
            last_lines = solution_lines[-3:]
            final_answer = None
            for line in reversed(last_lines):
                if '=' in line or ':' in line or 'answer' in line.lower() or 'result' in line.lower():
                    final_answer = line
                    break
            
            if final_answer:
                chain.add_response(final_answer)
            else:
                chain.add_response(solution_lines[-1] if solution_lines else "Completed the calculations.")
        
        return solution
        
    except Exception as e:
        error_msg = f"Error executing the math plan: {str(e)}"
        if chain:
            chain.add_reasoning(error_msg)
        return error_msg

@app.route('/api/message', methods=['POST'])
def receive_message():
    """Endpoint to receive messages"""
    message = request.json
    
    if not message:
        return jsonify({"error": "No message provided"}), 400
    
    # Check if reasoning is requested
    with_reasoning = message.get("reasoning", True)  # Default to reasoning on
    
    # Check if streaming is requested
    stream = message.get("stream", False)
    
    if stream:
        return Response(
            stream_with_context(process_message_stream(message, with_reasoning)),
            content_type='text/event-stream'
        )
    else:
        # Process the message synchronously
        try:
            response_content = process_message(message, with_reasoning)
            
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

def process_message_stream(message, with_reasoning=False):
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
        result = parse_math_operation(content, with_reasoning)
        
        # If direct parsing failed, use OpenAI to interpret the query
        if result is None:
            # Create a reasoning chain if needed
            chain = ReasoningChain() if with_reasoning else None
            
            if chain:
                chain.add_reasoning("I need to use OpenAI to better understand the mathematical query.")
            
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
            
            if chain:
                chain.add_reasoning(f"OpenAI extracted the mathematical expression: {math_expression}")
            
            # Try to parse the extracted expression
            result = parse_math_operation(math_expression, with_reasoning)
            
            # If still no result, use OpenAI to solve it
            if result is None:
                if chain:
                    chain.add_reasoning("I still couldn't parse a specific operation. I'll ask OpenAI to solve the complete problem.")
                
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a math assistant. Solve the mathematical problem and show your work step by step."},
                        {"role": "user", "content": content}
                    ],
                    max_tokens=150
                )
                
                result = response.choices[0].message.content.strip()
                
                if chain:
                    chain.add_response(result)
                    result = chain.get_detailed_explanation()
        
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

def process_message(message, with_reasoning=False):
    """Process the incoming message and generate a response"""
    content = message.get("content", "")
    
    # Check if reasoning is requested specifically in the message
    if message.get("reasoning", False):
        with_reasoning = True
    
    # Initialize the reasoning chain if needed
    chain = None
    if with_reasoning:
        try:
            from reasoning import ReasoningChain
            chain = ReasoningChain()
        except ImportError:
            print("Warning: Reasoning module not available.")
    
    # First, check for simple patterns that we can handle directly
    if chain:
        chain.add_reasoning(f"Received math query: '{content}'")
    
    # Try to parse it as a percentage operation (X% of Y)
    percentage_match = re.search(r'(\d+\.?\d*)%\s*of\s*(\d+\.?\d*)', content)
    if percentage_match:
        percent_value = float(percentage_match.group(1))
        base_value = float(percentage_match.group(2))
        if chain:
            chain.add_reasoning(f"I identified a percentage operation: {percent_value}% of {base_value}")
            result = (percent_value / 100) * base_value
            chain.add_calculation("percentage_of", 
                                {"percentage": percent_value, "value": base_value}, 
                                result)
            chain.add_response(f"{percent_value}% of {base_value} is {result}")
            return chain.get_detailed_explanation()
        else:
            return f"{percent_value}% of {base_value} is {(percent_value / 100) * base_value}"
    
    # Try to parse basic math operations using regex
    result = parse_math_operation(content, with_reasoning)
    if result is not None:
        return result
    
    # If it's potentially a complex problem, handle it with detailed reasoning
    if chain:
        chain.add_reasoning("This appears to be a complex math problem that needs more analysis.")
        return handle_complex_problem(content, chain)
    
    # If all else fails, use OpenAI to solve it
    try:
        if chain:
            chain.add_reasoning("I'll use OpenAI to better understand this mathematical query.")
        
        # More specialized system message for math problems
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": """You are a mathematical reasoning assistant that solves problems step by step.
                Always show your work and explain the mathematical operations you're performing.
                Break down complex problems into simple steps and show all calculations clearly.
                If you're using a formula, explain what the formula is and what each variable represents."""},
                {"role": "user", "content": f"Solve this math problem step by step, showing all calculations clearly: {content}"}
            ],
            temperature=0,
            max_tokens=500
        )
        
        result = response.choices[0].message.content.strip()
        
        if chain:
            # Extract key reasoning from the result
            for line in result.split('\n'):
                if line.strip():
                    chain.add_reasoning(line)
            chain.add_response(result.split('\n')[-1] if result.split('\n') else result)
            return chain.get_detailed_explanation()
        
        return result
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