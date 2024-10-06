
import time

class FeedbackManager:
    def __init__(self):
        self.feedback = None
        self.active = False

    def start_feedback_loop(self, prompt, callback, interval=1):
        print(f"Feedback loop started. {prompt}")
        self.active = True
        while self.active:
            feedback = input("Provide feedback (or type 'exit' to stop): ")
            if feedback.lower() == 'exit':
                self.active = False
            else:
                callback(feedback)
            time.sleep(interval)

    def stop_feedback_loop(self):
        self.active = False
        print("Feedback loop stopped.")

# Example usage:
# def process_feedback(feedback):
#     print(f"Received feedback: {feedback}")

# feedback_manager = FeedbackManager()
# feedback_manager.start_feedback_loop("How is the current operation?", process_feedback)
