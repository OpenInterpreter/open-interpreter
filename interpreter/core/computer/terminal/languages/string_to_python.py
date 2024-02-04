import ast
import os
# Define the python code string
python_code_string = """
import os
import datetime
import sys
import json
import math
import random
import re
import http.client
import urllib.request
import logging

def book_ticket():
    \"""
    This function books a ticket.
    \"""
    print("Ticket booked")

def cancel_ticket():
    \"""
    This function cancels a ticket.
    \"""
    print("Ticket cancelled")

def update_ticket():
    \"""
    This function updates a ticket.
    \"""
    print("Ticket updated")

def check_ticket_status():
    \"""
    This function checks the status of a ticket.
    \"""
    print("Checked ticket status")

def print_ticket():
    \"""
    This function prints a ticket.
    \"""
    print("Ticket printed")

def reserve_seat():
    \"""
    This function reserves a seat.
    \"""
    print("Seat reserved")

def modify_booking():
    \"""
    This function modifies a booking.
    \"""
    print("Booking modified")

def confirm_payment():
    \"""
    This function confirms payment for a booking.
    \"""
    print("Payment confirmed")

def generate_itinerary():
    \"""
    This function generates an itinerary.
    \"""
    print("Itinerary generated")

def send_confirmation_email():
    \"""
    This function sends a confirmation email.
    \"""
    print("Confirmation email sent")
"""

parsed_code = ast.parse(python_code_string)

# Initialize containers for different categories
import_statements = []
functions = []

# Traverse the AST
for node in ast.walk(parsed_code):
    # Check for import statements
    if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
        for alias in node.names:
            # Handling the alias in import statements
            if alias.asname:
                import_statements.append(f"import {alias.name} as {alias.asname}")
            else:
                import_statements.append(f"import {alias.name}")
    # Check for function definitions
    elif isinstance(node, ast.FunctionDef):
        func_info = {
            'name': node.name,
            'docstring': ast.get_docstring(node),
            'body': '\n    '.join(ast.unparse(stmt) for stmt in node.body[1:])  # Excludes the docstring
        }
        functions.append(func_info)

# Directory to save the function files
output_dir = "./function_files"
os.makedirs(output_dir, exist_ok=True)

# Generate a Python file for each function
for func in functions:
    file_content = '\n'.join(import_statements) + '\n\n'
    file_content += f"def {func['name']}():\n    \"\"\"{func['docstring']}\"\"\"\n    {func['body']}\n"
    
    # File path for the function
    file_path = os.path.join(output_dir, f"{func['name']}.py")
    
    # Write the function and imports to the file
    with open(file_path, "w") as file:
        file.write(file_content)

    print(f"Created file for function {func['name']}: {file_path}")
