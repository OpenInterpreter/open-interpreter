import interpreter, os
import streamlit as st


def load_api_key():
        """
        Loads the OpenAI API key from the .env file or 
        from the user's input and returns it
        """
        if not hasattr(st.session_state, "api_key"):
            st.session_state.api_key = None
        #you can define your API key in .env directly
        if os.path.exists(".env") and os.environ.get("OPENAI_API_KEY") is not None:
            user_api_key = os.environ["OPENAI_API_KEY"]
            st.sidebar.success("API key loaded from .env", icon="🚀")
        else:
            if st.session_state.api_key is not None:
                user_api_key = st.session_state.api_key
                st.sidebar.success("API key loaded from previous input", icon="🚀")
            else:
                user_api_key = st.sidebar.text_input(
                    label="#### Your OpenAI API key 👇", placeholder="sk-...", type="password"
                )
                if user_api_key:
                    st.session_state.api_key = user_api_key
        return user_api_key



class ChatBot():
    def __init__(self):
        user_api_key = load_api_key()
        os.environ["OPENAI_API_KEY"] = user_api_key
    
    def run(self):
        interpreter.auto_run = True
        interpreter.model = "gpt-3.5-turbo"
        interpreter.temperature = 0

        # Store LLM generated responses
        if "messages" not in st.session_state.keys():
            st.session_state.messages = [{"role": "assistant", "content": "How may I help you?"}]
            
        # Display chat messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])
            

        # User-provided prompt
        if prompt := st.chat_input():
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.write(prompt)
                

        # Generate a new response if last message is not from assistant
        if st.session_state.messages[-1]["role"] != "assistant":
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    response = generate_response(prompt) 
                    st.write(response[-1]["content"]) 
            message = {"role": "assistant", "content": response[-1]["content"]}
            st.session_state.messages.append(message)
            
    # Function for generating LLM response
def generate_response(prompt_input):
    messages = [{'role': 'user', 'content': prompt_input}]
    if not os.environ["OPENAI_API_KEY"]:
            st.warning("Please enter your OpenAI API key in the sidebar")
    else:
        messages = interpreter.chat(prompt_input, return_messages=True)
    return messages


if __name__ == "__main__":
    ChatBot().run()