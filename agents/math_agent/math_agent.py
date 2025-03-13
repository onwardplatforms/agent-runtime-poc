#!/usr/bin/env python3

import asyncio
import json
import time
import uuid
import os
import logging
from flask import Flask, request, jsonify, Response, stream_with_context
from dotenv import load_dotenv

from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.contents import ChatHistory
from semantic_kernel.contents.streaming_chat_message_content import StreamingChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole
from semantic_kernel.functions import KernelArguments

# Import our custom plugin
from plugins.math_plugin import MathPlugin

app = Flask(__name__)

# Load environment variables from .env file
load_dotenv()

AGENT_ID = "math-agent"
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    print("Error: OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
    exit(1)

# Define the system message for the math agent
SYSTEM_MESSAGE = """
You are a specialized AI math assistant with the following capabilities:
1. Breaking down complex math problems into steps by yourself
2. Performing mathematical calculations using the plugin functions provided to you
3. Thinking through problems carefully, step-by-step, identifying the core functions and logical steps
4. ALWAYS using available math functions for calculations rather than doing them manually

EXTREMELY IMPORTANT: You MUST ACTUALLY INVOKE the math plugin functions for ANY calculation. 
DO NOT just talk about using them - you MUST ACTUALLY CALL them.

Even for simple calculations like 2+2 or sqrt(625), you MUST INVOKE the plugin functions.
If you merely mention "I'll use math.Add" without actually calling it, the operation won't be performed.

HOW TO SOLVE PROBLEMS:
1. Start by thinking through the problem yourself considering what formula(s) may apply and asking clarifying questions when needed
2. ALWAYS break down the problem into individual calculation steps
3. For EACH step, you MUST INVOKE the appropriate math function
4. You need to say AND do: "I need to [operation], so I'll call math.[Function]"
5. At the end, always check your work before providing the final answer

For example, to solve "What is 5 + 8 divided by 2?":
- "First, I need to add 5 and 8, so I'll call math.Add(5, 8)" [ACTUALLY CALL THE FUNCTION]
- "Next, I need to divide 13 by 2, so I'll call math.Divide(13, 2)" [ACTUALLY CALL THE FUNCTION]
- "Therefore, 5 + 8 divided by 2 = 6.5."

DO NOT EXPLAIN WITHOUT DOING. You MUST invoke the functions, not just talk about them.
Always response in GitHub Flavored Markdown format.
"""

# Create a kernel for the agent
kernel = Kernel()

# Initialize the OpenAI service with the API key
try:
    from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion, OpenAIChatPromptExecutionSettings
    from semantic_kernel.filters import AutoFunctionInvocationContext, FilterTypes
    
    # Initialize chat service with appropriate settings
    chat_service = OpenAIChatCompletion(service_id="chat-gpt", ai_model_id="gpt-4o", api_key=API_KEY)
    
    # Add service to kernel
    kernel.add_service(chat_service)
    
    # Add a filter to track function calls
    @kernel.filter(filter_type=FilterTypes.AUTO_FUNCTION_INVOCATION)
    async def auto_function_invocation_filter(
        context: AutoFunctionInvocationContext, 
        next: callable
    ) -> None:
        # # Before function call
        # print(f"\n==== FUNCTION BEING CALLED ====")
        # print(f"Function: {context.function.name}")
        # print(f"Arguments: {context.arguments}")
        # print("================================\n")
        
        # Call the function
        await next(context)
        
        # # After function call
        # print(f"\n==== FUNCTION CALL RESULT ====")
        # print(f"Result: {context.function_result}")
        # print("==============================\n")
        
except ImportError:
    print("OpenAI service not available. Please install the openai package.")
    exit(1)

# Add our math plugin to the kernel
kernel.add_plugin(MathPlugin(), plugin_name="math")

# Create a chat function for handling math queries
chat_function = kernel.add_function(
    prompt="{{$chat_history}}{{$user_input}}",
    plugin_name="MathAgent",
    function_name="SolveMathProblem",
)


@app.route('/api/message', methods=['POST'])
def receive_message():
    """Endpoint to receive messages from the runtime or external calls."""
    
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
        # Process synchronously
        try:
            response_content = process_message(message)
            response = {
                "messageId": str(uuid.uuid4()),
                "conversationId": message.get("conversationId", ""),
                "senderId": AGENT_ID,
                "recipientId": message.get("senderId", ""),
                "content": response_content,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "type": "Text"
            }
            return jsonify(response), 200
        except Exception as e:
            print(f"Error processing message: {e}")
            return jsonify({"error": str(e)}), 500


def stream_with_context(generator):
    """Helper that yields SSE lines and ends with [DONE]."""
    try:
        for chunk in generator:
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        print(f"Error in streaming: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"


def process_message_stream(message):
    """Process a message from the client and stream the response."""
    content = message.get("content", "")
    conversation_id = message.get("conversationId", "")
    sender_id = message.get("senderId", "")
    message_id = str(uuid.uuid4())

    # Create a chat history for the semantic kernel
    history = ChatHistory()
    history.add_system_message(SYSTEM_MESSAGE)
    
    # If chat history is provided, add it to the history
    chat_history = message.get("chatHistory", [])
    for msg in chat_history:
        if msg.get("role") == "user":
            history.add_user_message(msg.get("content", ""))
        elif msg.get("role") == "assistant":
            history.add_assistant_message(msg.get("content", ""))
            
    # Add user message
    history.add_user_message(content)

    # Yield an initial chunk to indicate the calculation has started
    yield {
        "messageId": message_id,
        "conversationId": conversation_id,
        "senderId": AGENT_ID,
        "recipientId": sender_id,
        "content": "",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "type": "Text",
        "chunk": "ƒ(x) calling math-agent...",
        "complete": False
    }
    
    try:
        # Setup execution settings with explicit function calling enabled
        settings = OpenAIChatPromptExecutionSettings(
            service_id="chat-gpt",
            function_choice_behavior=FunctionChoiceBehavior.Auto(),
            max_tokens=2000
        )
        
        # Set up for streaming
        accumulated_response = ""
        function_calls = []
        
        # Create an asyncio event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Stream the response from chat service
        for msg in loop.run_until_complete(
            stream_sk_response(chat_service, history, settings)
        ):
            # Get the message content
            chunk_text = str(msg)
            
            # Check for function call markers in the text
            if "ƒ(x) calling" in chunk_text:
                function_calls.append(chunk_text)
                
                # Yield the function call as a separate chunk
                yield {
                    "messageId": message_id,
                    "conversationId": conversation_id,
                    "senderId": AGENT_ID,
                    "recipientId": sender_id,
                    "content": "",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "type": "Text",
                    "chunk": chunk_text,
                    "complete": False
                }
                continue
                
            # Accumulate the response
            accumulated_response += chunk_text
            
            # Yield the chunk
            yield {
                "messageId": message_id,
                "conversationId": conversation_id,
                "senderId": AGENT_ID,
                "recipientId": sender_id,
                "content": "",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "type": "Text",
                "chunk": chunk_text,
                "complete": False
            }
            
            # Small delay to ensure smooth streaming
            time.sleep(0.01)
            
        # Final chunk with the complete response
        yield {
            "messageId": message_id,
            "conversationId": conversation_id,
            "senderId": AGENT_ID,
            "recipientId": sender_id,
            "content": accumulated_response,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "type": "Text",
            "chunk": None,
            "complete": True,
            "response": accumulated_response
        }
    except Exception as e:
        print(f"Error in streaming process: {e}")
        import traceback
        traceback.print_exc()
        
        # Yield an error response
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


async def stream_sk_response(chat_service, chat_history, settings):
    """Stream the response from Semantic Kernel's chat service."""
    async for chunk in chat_service.get_streaming_chat_message_content(
        chat_history=chat_history,
        settings=settings,
        kernel=kernel,
    ):
        yield chunk


def process_message(message):
    """Process a message synchronously."""
    
    content = message.get("content", "")
    
    # Create a chat history for the semantic kernel
    history = ChatHistory()
    history.add_system_message(SYSTEM_MESSAGE)
    
    # If chat history is provided, add it to the history
    chat_history = message.get("chatHistory", [])
    for msg in chat_history:
        if msg.get("role") == "user":
            history.add_user_message(msg.get("content", ""))
        elif msg.get("role") == "assistant":
            history.add_assistant_message(msg.get("content", ""))
    
    try:
        # Add the user message
        history.add_user_message(content)
        
        # Setup execution settings with explicit function calling enabled
        settings = OpenAIChatPromptExecutionSettings(
            service_id="chat-gpt",
            function_choice_behavior=FunctionChoiceBehavior.Auto(),
            max_tokens=2000
        )
        
        # Create an asyncio event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Get response from the chat service
        result = loop.run_until_complete(
            chat_service.get_chat_message_content(
                chat_history=history,
                settings=settings,
                kernel=kernel
            )
        )
        
        return str(result)
    
    except Exception as e:
        print(f"Error processing message: {e}")
        import traceback
        traceback.print_exc()
        return f"I encountered an error while processing your math query: {str(e)}"


if __name__ == "__main__":
    print("Starting Math Agent with ID:", AGENT_ID)
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    app.run(host="0.0.0.0", port=5004)


