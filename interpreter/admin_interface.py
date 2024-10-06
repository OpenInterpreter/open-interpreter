
from flask import Flask
from flask_admin import Admin
import streamlit as st
import threading

# Flask Admin for Server Monitoring
app = Flask(__name__)
admin = Admin(app, name='GodMode-Interpreter Admin', template_mode='bootstrap3')

@app.route('/')
def index():
    return "Welcome to the GodMode-Interpreter Admin Panel!"

def run_flask():
    app.run(port=5000, debug=True)

# Streamlit Dashboard for Monitoring
def run_streamlit():
    st.title("GodMode-Interpreter Dashboard")
    st.header("Real-Time Monitoring")
    
    # Placeholder metrics for demonstration purposes
    st.metric("Total Commands Executed", 150)
    st.metric("Active Sessions", 5)
    st.metric("Average Response Time", "0.35s")
    
    st.write("More real-time statistics will be available here!")

if __name__ == "__main__":
    # Run Flask and Streamlit on separate threads
    flask_thread = threading.Thread(target=run_flask)
    streamlit_thread = threading.Thread(target=run_streamlit)

    flask_thread.start()
    streamlit_thread.start()
