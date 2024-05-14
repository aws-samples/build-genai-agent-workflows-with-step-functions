import jinja2
import logging

logger = logging.getLogger()


def apply_prompt_template(messages):
    # Define the Jinja2 template
    prompt_template = """\
{% if messages[0]['role'] == 'system' %}
    {% set loop_messages = messages[1:] %}
    {% set system_message = messages[0]['content'].strip() + '\n\n' %}
{% else %}
    {% set loop_messages = messages %}
    {% set system_message = '' %}
{% endif %}

{{ bos_token }}
{% for message in loop_messages %}
    {% if (message['role'] == 'user') != (loop.index0 % 2 == 0) %}
        {{ raise_exception('Conversation roles must alternate user/assistant/user/assistant/...') }}
    {% endif %}
    
    {% if loop.index0 == 0 %}
        {% set content = system_message + message['content'] %}
    {% else %}
        {% set content = message['content'] %}
    {% endif %}
    
    {% if message['role'] == 'user' %}
        {{ '[INST] ' + content.strip() + ' [/INST]' }}
    {% elif message['role'] == 'assistant' %}
        {{ ' ' + content.strip() + eos_token }}
    {% endif %}
{% endfor %}
"""

    template = jinja2.Template(prompt_template)
    rendered_prompt = template.render(
        bos_token="<s>", eos_token="</s>", messages=messages
    )

    return rendered_prompt.strip()


def handler(event, context):
    logger.info(event)

    return apply_prompt_template(event["messages"])
