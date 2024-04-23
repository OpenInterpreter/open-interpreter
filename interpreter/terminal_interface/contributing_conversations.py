import os
import json


contribute_cache_path = os.path.join(
    os.path.expanduser("~"), ".cache", "open-interpreter", "contribute.json"
)


def ask_user_to_run_contribute():
    print("---")
    print("not contributing current")
    print("Run --contribute_conversation to contribute the current conversation!")
    print()


def send_past_conversations(interpreter):
    print("sending all past conversations!")


def set_send_future_conversations(interpreter, should_send_future):
    if should_send_future:
        print("sending!")
    else:
        print("not sending!")


def ask_user_to_contribute_past():
    print("do you want to contribute all past conversations?")
    response = input("(y/n) ")
    return response.lower() == "y"


def ask_user_to_contribute_future():
    print("do you want to contribute all future conversations?")
    response = input("(y/n) ")
    return response.lower() == "y"


def contribute_conversation_launch_logic(interpreter):
    contribution_cache = get_contribute_cache_contents()
    displayed_contribution_message = contribution_cache["asked_to_run_contribute"]
    contribute_current = interpreter.contribute_conversation

    if displayed_contribution_message:
        if contribute_current:
            # second launch, --contribute-conversation.
            contribute_past_and_future_logic(interpreter, contribution_cache)
        else:
            # second launch, no --contribute-conversation.
            # continue launching as normal!
            # no need to modify contribution_cache because we're not asking about
            # past conversations and we've already displayed the contribution message.
            return
    else:
        if contribute_current:
            # first launch, --contribute-conversation.
            contribute_past_and_future_logic(interpreter, contribution_cache)
        else:
            # first launch, no --contribute-conversation.
            ask_user_to_run_contribute()
            contribution_cache["asked_to_run_contribute"] = True

    write_to_contribution_cache(contribution_cache)


# modifies the contribution cache!
def contribute_past_and_future_logic(interpreter, contribution_cache):
    if not contribution_cache["asked_to_contribute_past"]:
        contribute_past = ask_user_to_contribute_past()
        if contribute_past:
            send_past_conversations(interpreter)

    # set asked_to_contribute_past to True no matter what!
    contribution_cache["asked_to_contribute_past"] = True

    contributing_future = interpreter.contributing_future_conversations
    if not contributing_future:
        contribute_future = ask_user_to_contribute_future()
        if contribute_future:
            set_send_future_conversations(interpreter, True)
        else:
            set_send_future_conversations(interpreter, False)


# Returns a {"asked_to_run_contribute": bool, "asked_to_contribute_past": bool}.
# Writes the contribution cache file if it doesn't already exist.
def get_contribute_cache_contents():
    if not os.path.exists(contribute_cache_path):
        default_dict = {
            "asked_to_contribute_past": False,
            "asked_to_run_contribute": False,
        }
        with open(contribute_cache_path, "a") as file:
            file.write(json.dumps(default_dict))
        return default_dict

    with open(contribute_cache_path, "r") as file:
        contribute_cache = json.load(file)
        return contribute_cache


# Takes in a {"asked_to_run_contribute": bool, "asked_to_contribute_past": bool}
def write_to_contribution_cache(contribution_cache):
    with open(contribute_cache_path, "w") as file:
        json.dump(contribution_cache, file)


