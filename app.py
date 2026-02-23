import streamlit as st
import google.generativeai as genai
import os
from typing import List, Dict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure the page
st.set_page_config(
    page_title="Gemini AI Chatbot",
    page_icon="🤖",
    layout="centered"
)

def initialize_gemini():
    """Initialize Gemini AI with API key"""
    try:
        # Try to get API key from environment variable first
        api_key = os.getenv("GOOGLE_API_KEY")
        
        if not api_key:
            # If not in environment, ask user to input it
            api_key = st.sidebar.text_input(
                "Enter your Google AI API Key:", 
                type="password",
                help="Get your API key from https://aistudio.google.com/app/apikey"
            )
        
        if api_key:
            genai.configure(api_key=api_key)
            return True
        return False
    except Exception as e:
        st.error(f"Error initializing Gemini: {str(e)}")
        return False

def generate_response(prompt: str, conversation_history: List[Dict] = None) -> str:
    """Generate response using Gemini AI"""
    try:
        model = genai.GenerativeModel('gemini-2.5-flash-lite')
        
        # Build context from conversation history
        if conversation_history:
            context = "\n".join([
                f"User: {msg['user']}\nAssistant: {msg['assistant']}" 
                for msg in conversation_history[-5:]  # Last 5 exchanges for context
            ])
            full_prompt = f"Previous conversation:\n{context}\n\nCurrent question: {prompt}"
        else:
            full_prompt = prompt
        
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return f"Error generating response: {str(e)}"

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
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate and display assistant response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = generate_response(prompt, st.session_state.conversation_history)
            st.markdown(response)
        
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})
        
        # Update conversation history for context
        st.session_state.conversation_history.append({
            "user": prompt,
            "assistant": response
        })

if __name__ == "__main__":
    main()