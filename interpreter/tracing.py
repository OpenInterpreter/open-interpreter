def save_message_trace_to_wandb(messages):
    import wandb
    from wandb.sdk.data_types.trace_tree import Trace

    wandb.init(project="open-interpreter")

    session_span = Trace(
        name="Agent Session",
        kind="agent",
        start_time_ms=messages[0]['timestamp'],
        end_time_ms=messages[-1]["end_time_ms"] if "end_time_ms" in messages[-1] else messages[-1]["timestamp"]
    )

    interaction_span = None
    for i, _ in enumerate(messages):
        message = messages[i]
        role = message["role"]
        if role == "user":
            if interaction_span:
                interaction_span.add_inputs_and_outputs(
                    inputs={"input": user_input}, outputs={"output": assistant_output}
                )
                session_span.add_child(interaction_span)
                interaction_span.log(name="open-interpreter")
                interaction_span = Trace(
                            name="Interaction",
                            kind="chain",
                            status_code="success",
                            start_time_ms=message["timestamp"],
                            end_time_ms=message["end_time_ms"]
                        )

            else:
                interaction_span = Trace(
                            name="Interaction",
                            kind="chain",
                            status_code="success",
                            start_time_ms=message["timestamp"],
                            end_time_ms=message["end_time_ms"]
                        )
            user_input = message["content"]

        if role == "assistant":
            assistant_output = message["content"]
            assistant_timestamp = message["timestamp"]
            if "function_call" in message:
                function_meta = dict(message["function_call"])
                print(function_meta)

        if role == "function":
            function_output = message["content"]
            tool_span = Trace(
                name=message["name"],
                kind="tool",
                status_code="success",
                start_time_ms=assistant_timestamp,
                end_time_ms=message["timestamp"],
                inputs={"input": assistant_output},
                outputs={"output": function_output},
                metadata=function_meta
            )
            interaction_span.add_child(tool_span)

    # Handle the last interaction span after the loop.
    if interaction_span:
        interaction_span.add_inputs_and_outputs(
            inputs={"input": user_input}, outputs={"output": assistant_output}
        )
        session_span.add_child(interaction_span)
        interaction_span.log(name="open-interpreter")

    session_span.log(name="open-interpreter-2")
    wandb.finish()
    return None
