from aws_cdk import (
    Duration,
    aws_bedrock as bedrock,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_lambda_python_alpha as lambda_python,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
)
from constructs import Construct
import builtins
import typing
import json


def add_bedrock_retries(task):
    task.add_retry(
        errors=["ThrottlingException"],
        interval=Duration.seconds(5),
        max_delay=Duration.seconds(15),
    )


def get_prepare_messages_step(
    scope: Construct,
    id: builtins.str,
    user_message: builtins.str,
    include_previous_conversation_in_prompt: bool,
    initial_assistant_text: typing.Optional[str] = "",
    input_json_path: typing.Optional[str] = "$.model_inputs",
    output_json_path: typing.Optional[str] = "$.model_outputs",
):
    messages = [
        {
            "role": "user",
            "content": user_message,
        }
    ]

    if initial_assistant_text:
        messages.append(
            {
                "role": "assistant",
                "content": initial_assistant_text,
            }
        )

    format_prompt = sfn.Pass(
        scope,
        id + " (Prepare Messages)",
        parameters={
            "messages": messages,
        },
        result_path=input_json_path,
    )
    if include_previous_conversation_in_prompt:
        insert_conversation = sfn.Pass(
            scope,
            id + " (Include Previous Messages)",
            parameters={
                "messages": sfn.JsonPath.array(
                    sfn.JsonPath.string_at(f"{output_json_path}.conversation"),
                    sfn.JsonPath.string_at(f"{input_json_path}.messages"),
                ),
            },
            result_path=input_json_path,
        )
        format_prompt = format_prompt.next(insert_conversation)
    return format_prompt


def get_format_prompt_step(
    scope: Construct,
    id: builtins.str,
    output_key: builtins.str = "prompt",
    flatten_messages: typing.Optional[bool] = False,
    input_json_path: typing.Optional[str] = "$.model_inputs",
    output_json_path: typing.Optional[str] = "$.model_outputs",
):

    format_prompt_lambda = lambda_python.PythonFunction(
        scope,
        "".join(id.split()) + "Function",
        runtime=lambda_.Runtime.PYTHON_3_12,
        entry="functions/generic/format_prompt",
        memory_size=256,
    )

    format_prompt = tasks.LambdaInvoke(
        scope,
        id + " (Formate Prompt)",
        lambda_function=format_prompt_lambda,
        payload=sfn.TaskInput.from_object(
            {
                "messages": (
                    sfn.JsonPath.object_at(f"{input_json_path}.messages[*][*]")
                    if flatten_messages
                    else sfn.JsonPath.object_at(f"{input_json_path}.messages")
                ),
            }
        ),
        result_selector={"text": sfn.JsonPath.string_at("$.Payload")},
        result_path=output_json_path + "." + output_key,
    )
    add_bedrock_retries(format_prompt)
    return format_prompt


def get_invoke_model_step(
    scope: Construct,
    id: builtins.str,
    model_id: bedrock.FoundationModelIdentifier = bedrock.FoundationModelIdentifier.MISTRAL_MIXTRAL_8_X7_B_INSTRUCT_V0_1,
    max_tokens_to_sample: typing.Optional[int] = 512,
    temperature: typing.Optional[float] = 1,
    input_json_path: typing.Optional[str] = "$.model_inputs",
    output_json_path: typing.Optional[str] = "$.model_outputs",
):
    invoke_model = tasks.BedrockInvokeModel(
        scope,
        id + " (Invoke Model)",
        model=bedrock.FoundationModel.from_foundation_model_id(
            scope,
            "Model",
            model_id,
        ),
        body=sfn.TaskInput.from_object(
            {
                "prompt": sfn.JsonPath.object_at(f"{input_json_path}.prompt.text"),
                "temperature": temperature,
                "max_tokens": max_tokens_to_sample,
            }
        ),
        result_selector={
            "role": "assistant",
            "content": sfn.JsonPath.string_at("$.Body.outputs[0].text"),
        },
        result_path=output_json_path,
    )
    add_bedrock_retries(invoke_model)
    return invoke_model


def get_extract_response_step(
    scope: Construct,
    id: builtins.str,
    user_message: builtins.str,
    initial_assistant_text: typing.Optional[str] = "",
    flatten_messages: typing.Optional[bool] = False,
    pass_conversation: typing.Optional[bool] = True,
    input_json_path: typing.Optional[str] = "$.model_inputs",
    output_json_path: typing.Optional[str] = "$.model_outputs",
):
    response_value = sfn.JsonPath.string_at(f"{output_json_path}.content")
    if initial_assistant_text:
        response_value = sfn.JsonPath.format(
            "{}{}", initial_assistant_text, response_value
        )

    extract_response_parameters = {
        "prompt": user_message,
        "response": response_value,
        "conversation": sfn.JsonPath.array(
            (
                sfn.JsonPath.string_at(f"{input_json_path}.messages[*][*]")
                if flatten_messages
                else sfn.JsonPath.string_at(f"{input_json_path}.messages")
            ),
            sfn.JsonPath.array(sfn.JsonPath.string_at(output_json_path)),
        ),
    }
    if not pass_conversation:
        extract_response_parameters.pop("conversation")

    extract_response = sfn.Pass(
        scope,
        id + " (Extract Model Response)",
        parameters=extract_response_parameters,
        result_path=output_json_path,
    )

    if pass_conversation:
        prepare_outputs = sfn.Pass(
            scope,
            id + " (Prepare Output)",
            parameters={
                "prompt": sfn.JsonPath.string_at(f"{output_json_path}.prompt"),
                "response": sfn.JsonPath.string_at(f"{output_json_path}.response"),
                "conversation": sfn.JsonPath.object_at(
                    f"{output_json_path}.conversation[*][*]"
                ),
            },
            result_path=output_json_path,
        )
        extract_response = extract_response.next(prepare_outputs)

    return extract_response


def get_invoke_chain(
    scope: Construct,
    id: builtins.str,
    user_message: builtins.str,
    model_id: bedrock.FoundationModelIdentifier = bedrock.FoundationModelIdentifier.MISTRAL_MIXTRAL_8_X7_B_INSTRUCT_V0_1,
    initial_assistant_text: typing.Optional[str] = "",
    include_initial_assistant_text_in_response: typing.Optional[bool] = True,
    max_tokens_to_sample: typing.Optional[int] = 250,
    temperature: typing.Optional[float] = 1,
    include_previous_conversation_in_prompt: typing.Optional[bool] = True,
    pass_conversation: typing.Optional[bool] = True,
    input_json_path: typing.Optional[str] = "$.model_inputs",
    output_json_path: typing.Optional[str] = "$.model_outputs",
):
    if initial_assistant_text and pass_conversation:
        raise ValueError(
            'initial_assistant_text cannot be used with pass_conversation. This combination results in a runtime error from Bedrock: `messages: roles must alternate between "user" and "assistant", but found multiple "assistant" roles in a row`'
        )

    prepare_messages = get_prepare_messages_step(
        scope,
        id,
        user_message,
        include_previous_conversation_in_prompt=include_previous_conversation_in_prompt,
        initial_assistant_text=initial_assistant_text,
        input_json_path=input_json_path,
        output_json_path=output_json_path,
    )

    format_prompt = get_format_prompt_step(
        scope,
        id,
        output_key="prompt",
        flatten_messages=include_previous_conversation_in_prompt,
        input_json_path=input_json_path,
        output_json_path=input_json_path,
    )

    invoke_model = get_invoke_model_step(
        scope,
        id,
        model_id=model_id,
        max_tokens_to_sample=max_tokens_to_sample,
        temperature=temperature,
        input_json_path=input_json_path,
        output_json_path=output_json_path,
    )

    extract_response = get_extract_response_step(
        scope,
        id,
        user_message,
        initial_assistant_text=(
            initial_assistant_text if include_initial_assistant_text_in_response else ""
        ),
        flatten_messages=include_previous_conversation_in_prompt,
        pass_conversation=pass_conversation,
        input_json_path=input_json_path,
        output_json_path=output_json_path,
    )

    return (
        prepare_messages.next(format_prompt).next(invoke_model).next(extract_response)
    )


def get_json_response_parser_step(
    scope: Construct,
    id: builtins.str,
    json_schema: typing.Any,
    output_key: builtins.str,
    result_path: builtins.str,
):
    initialize_parse_attempt_counter = sfn.Pass(
        scope,
        id + " - Initialize Parsing Error Counter",
        parameters={"parse_error_count": 0},
        result_path="$.error_state",
    )

    parser_lambda = lambda_python.PythonFunction(
        scope,
        "".join(id.split()) + "Function",
        runtime=lambda_.Runtime.PYTHON_3_12,
        entry="functions/generic/parse_json_response",
        memory_size=256,
    )

    parser_job = tasks.LambdaInvoke(
        scope,
        id,
        lambda_function=parser_lambda,
        payload=sfn.TaskInput.from_object(
            {
                "response_string": sfn.JsonPath.string_at("$.model_outputs.response"),
                "json_schema": json_schema,
            }
        ),
        result_selector={
            output_key: sfn.JsonPath.object_at("$.Payload"),
        },
        result_path=result_path,
    )

    parse_error_message = sfn.Pass(
        scope,
        id + " - Parse Error Message",
        parameters={
            "parsed_error": sfn.JsonPath.string_to_json(
                sfn.JsonPath.string_at("$.caught_error.Cause")
            ),
            "parse_error_count": sfn.JsonPath.math_add(
                sfn.JsonPath.number_at("$.error_state.parse_error_count"), 1
            ),
        },
        result_path="$.error_state",
    )

    fix_json = get_invoke_chain(
        scope,
        id + " - Fix JSON",
        user_message=sfn.JsonPath.format(
            f"""I attempted to validate your response against my JSON schema, but received the following error inside <error></error> XML tags.
<error>
{{}}

{{}}
</error>

Here is my JSON schema, inside <schema></schema> XML tags:
<schema>
{json.dumps(json_schema, indent=2).replace("{", chr(92) + "{").replace("}", chr(92) + "}")}
</schema>

Please try to fix errors in the JSON response you gave previously and return a new JSON response that complies with the JSON schema.
Do NOT include any explanation, comments, apology, or markdown style code-back-ticks.
Remember - only return a valid JSON object.""",
            sfn.JsonPath.string_at("$.error_state.parsed_error.errorType"),
            sfn.JsonPath.string_at("$.error_state.parsed_error.errorMessage"),
        ),
        max_tokens_to_sample=500,
        temperature=0,
        include_previous_conversation_in_prompt=True,
        pass_conversation=True,
    )

    attempt_to_fix_json = parse_error_message.next(
        sfn.Choice(scope, id + " - Too many attempts to fix?")
        .when(
            sfn.Condition.number_less_than("$.error_state.parse_error_count", 3),
            fix_json.next(parser_job),
        )
        .otherwise(sfn.Fail(scope, id + " - Fail"))
    )

    parser_job.add_catch(
        handler=attempt_to_fix_json,
        errors=[sfn.Errors.TASKS_FAILED],
        result_path="$.caught_error",
    )

    return initialize_parse_attempt_counter.next(parser_job)
