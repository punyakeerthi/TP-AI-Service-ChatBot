import streamlit as st
import google.generativeai as genai
import os
import logging
import time
import json
import threading
import signal
from typing import List, Dict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging for console output (Streamlit apps)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Only console output for Streamlit
    ]
)
logger = logging.getLogger(__name__)

# Configure the page
st.set_page_config(
    page_title="Gemini AI Chatbot",
    page_icon="🤖",
    layout="centered"
)

def initialize_gemini():
    """Initialize Gemini AI with API key"""
    logger.info("Initializing Gemini AI...")
    try:
        # Try to get API key from environment variable first
        api_key = os.getenv("GOOGLE_API_KEY")
        
        if not api_key:
            logger.info("No API key found in environment variables")
            # If not in environment, ask user to input it
            api_key = st.sidebar.text_input(
                "Enter your Google AI API Key:", 
                type="password",
                help="Get your API key from https://aistudio.google.com/app/apikey"
            )
        else:
            logger.info("API key found in environment variables")
        
        if api_key:
            genai.configure(api_key=api_key)
            logger.info("Gemini AI initialized successfully")
            return True
        logger.warning("No API key provided")
        return False
    except Exception as e:
        logger.error(f"Error initializing Gemini: {str(e)}")
        logger.exception("Full traceback for Gemini initialization error:")
        st.error(f"Error initializing Gemini: {str(e)}")
        return False

def generate_response(prompt: str, conversation_history: List[Dict] = None) -> str:
    """Generate response using Gemini AI with comprehensive logging and timeout handling"""
    start_time = time.time()
    model_name = 'gemini-2.5-flash-lite'
    
    # Log before LLM call
    logger.info(f"LLM Call Started - Model: {model_name}")
    logger.info(f"Input prompt length: {len(prompt)} characters")
    logger.info(f"Conversation history length: {len(conversation_history) if conversation_history else 0} exchanges")
    
    try:
        # Initialize model with timeout considerations
        logger.info("Initializing Gemini model...")
        model = genai.GenerativeModel(model_name)
        logger.info("Model initialized successfully")
        
        # Build context from conversation history
        if conversation_history:
            context = "\n".join([
                f"User: {msg['user']}\nAssistant: {msg['assistant']}" 
                for msg in conversation_history[-5:]  # Last 5 exchanges for context
            ])
            full_prompt = f"Previous conversation:\n{context}\n\nCurrent question: {prompt}"
            logger.info(f"Context added from last {min(5, len(conversation_history))} exchanges")
        else:
            full_prompt = prompt
            logger.info("No conversation history provided")
        
        logger.info(f"Final prompt length: {len(full_prompt)} characters")
        logger.debug(f"Full prompt content: {json.dumps(full_prompt[:500])}...")  # Log first 500 chars
        
        # Make the LLM call with timeout handling
        logger.info("Sending request to Gemini API...")
        
        # Create a container for the response
        response_container = {'response': None, 'error': None, 'completed': False}
        
        def api_call():
            try:
                logger.info("API call thread started...")
                response = model.generate_content(full_prompt)
                response_container['response'] = response
                response_container['completed'] = True
                logger.info("API call completed successfully in thread")
            except Exception as e:
                logger.error(f"API call failed in thread: {str(e)}")
                response_container['error'] = e
                response_container['completed'] = True
        
        # Start API call in a separate thread
        api_thread = threading.Thread(target=api_call)
        api_thread.daemon = True
        api_thread.start()
        
        # Wait for completion with timeout monitoring
        timeout_seconds = 30
        check_interval = 1
        elapsed = 0
        
        logger.info(f"Waiting for API response (timeout: {timeout_seconds}s)...")
        
        while elapsed < timeout_seconds and not response_container['completed']:
            time.sleep(check_interval)
            elapsed += check_interval
            if elapsed % 5 == 0:  # Log every 5 seconds
                logger.info(f"Still waiting... ({elapsed}s elapsed)")
        
        api_thread.join(timeout=1)  # Give thread a moment to clean up
        
        if not response_container['completed']:
            logger.error(f"API call timed out after {timeout_seconds} seconds")
            logger.error("This could indicate:")
            logger.error("- Network connectivity issues")
            logger.error("- API rate limiting")
            logger.error("- Gemini service unavailability")
            logger.error("- Firewall or proxy blocking the request")
            return "Error: API call timed out. Please check your network connection and try again."
        
        if response_container['error']:
            raise response_container['error']
        
        response = response_container['response']
        
        # Calculate metrics
        end_time = time.time()
        response_time = end_time - start_time
        response_length = len(response.text) if response.text else 0
        
        # Log successful response
        logger.info("LLM Call Successful")
        logger.info(f"Response time: {response_time:.2f} seconds")
        logger.info(f"Response length: {response_length} characters")
        logger.info(f"Response preview: {response.text[:100] if response.text else 'Empty response'}...")
        
        # Log additional response metadata if available
        if hasattr(response, 'usage_metadata'):
            try:
                usage_info = {
                    'prompt_token_count': getattr(response.usage_metadata, 'prompt_token_count', 'N/A'),
                    'candidates_token_count': getattr(response.usage_metadata, 'candidates_token_count', 'N/A'),
                    'total_token_count': getattr(response.usage_metadata, 'total_token_count', 'N/A')
                }
                logger.info(f"Token usage: {json.dumps(usage_info)}")
            except Exception as token_error:
                logger.warning(f"Could not extract token usage: {str(token_error)}")
        
        logger.info("LLM Call Completed Successfully")
        return response.text
        
    except Exception as e:
        end_time = time.time()
        response_time = end_time - start_time
        
        # Log failure details
        logger.error("LLM Call Failed")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        logger.error(f"Failed after: {response_time:.2f} seconds")
        logger.error(f"Input prompt that caused error: {prompt[:200]}...")  # Log first 200 chars of failing prompt
        
        # Check for specific error types
        error_str = str(e).lower()
        if "rate limit" in error_str or "quota" in error_str:
            logger.error("RATE LIMITING DETECTED - Wait before making more requests")
        elif "network" in error_str or "connection" in error_str:
            logger.error("NETWORK ISSUE DETECTED - Check internet connection")
        elif "authentication" in error_str or "api key" in error_str:
            logger.error("AUTHENTICATION ISSUE - Check API key validity")
        elif "timeout" in error_str:
            logger.error("API TIMEOUT - Service may be slow or unavailable")
        else:
            logger.error("UNKNOWN ERROR - Check error details above")
        
        # Log stack trace for debugging
        logger.exception("Full error traceback:")
        
        error_response = f"Error generating response: {str(e)}"
        logger.info(f"Returning error response: {error_response}")
        return error_response

def main():
    """Main application function"""
    
    # Title and description
    st.title("🤖 Gemini AI Chatbot")
    st.markdown("Ask me anything! I'm powered by Google's Gemini AI.")
    
    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "conversation_history" not in st.session_state:
        st.session_state.conversation_history = []
    
    # Initialize Gemini
    if not initialize_gemini():
        st.warning("Please configure your Google AI API key to start chatting!")
        st.info("You can get your API key from: https://aistudio.google.com/app/apikey")
        return
    
    # Sidebar with information
    with st.sidebar:
        st.header("About Chatbot")
        st.markdown("""
        This chatbot uses Google's Gemini AI to answer your questions.
        
        **Features:**
        - Natural language conversations
        - Context-aware responses
        - Clean and intuitive interface
        
        **Tips:**
        - Ask specific questions for better responses
        - The bot remembers your last 5 exchanges
        - Clear chat history using the button below
        """)
        
        if st.button("Clear Chat History", type="secondary"):
            st.session_state.messages = []
            st.session_state.conversation_history = []
            st.success("Chat history cleared!")
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("What would you like to know?"):
        logger.info(f"New user message received: {prompt[:100]}...")  # Log first 100 chars
        logger.info(f"Current conversation length: {len(st.session_state.conversation_history)} exchanges")
        
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate and display assistant response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                logger.info("Starting response generation...")
                response = generate_response(prompt, st.session_state.conversation_history)
                logger.info("Response generation completed")
            st.markdown(response)
        
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})
        
        # Update conversation history for context
        st.session_state.conversation_history.append({
            "user": prompt,
            "assistant": response
        })
        
        logger.info(f"Conversation updated. Total exchanges: {len(st.session_state.conversation_history)}")

if __name__ == "__main__":
    main()