from aws_cdk import (
    App,
    Environment,
)
from stacks.webapp_stack import WebappStack
from stacks.story_writer_stack import StoryWriterStack
import os


app = App()
env = Environment(account=os.environ["CDK_DEFAULT_ACCOUNT"], region="us-west-2")
WebappStack(
    app,
    "PromptChaining-StreamlitWebapp",
    env=env,
    parent_domain="genai.awsguru.dev",
)
StoryWriterStack(
    app,
    "PromptChaining-StoryWriterDemo",
    env=env,
)

app.synth()
