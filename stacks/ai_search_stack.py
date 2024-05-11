from aws_cdk import (
    Duration,
    Stack,
    aws_lambda as lambda_,
    aws_lambda_python_alpha as lambda_python,
    aws_iam as iam,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
)
from constructs import Construct


class AISearchStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create IAM role for Lambda function
        lambda_role = iam.Role(
            self, "LambdaRole", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )

        # Grant lambda basic execution role
        lambda_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaBasicExecutionRole"
            )
        )

        # Grant permission to invoke Claude v3 Haiku model
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["bedrock:InvokeModel"],
                resources=["arn:aws:bedrock:*::foundation-model/*"],
            )
        )

        understand_user_question_lambda = lambda_python.PythonFunction(
            self,
            "UnderstandUserQuestionAgent",
            entry="functions/ai_search/understand_user_question",
            runtime=lambda_.Runtime.PYTHON_3_12,
            timeout=Duration.seconds(60),
            memory_size=1024,
            role=lambda_role,
        )

        query_search_engine_lambda = lambda_python.PythonFunction(
            self,
            "QuerySearchEngineAgent",
            entry="functions/ai_search/query_search_engine",
            runtime=lambda_.Runtime.PYTHON_3_12,
            timeout=Duration.seconds(60),
            memory_size=1024,
        )

        scrap_web_pages_lambda = lambda_python.PythonFunction(
            self,
            "ScrapWebPagesAgent",
            entry="functions/ai_search/scrap_web_pages",
            runtime=lambda_.Runtime.PYTHON_3_12,
            timeout=Duration.seconds(120),
            memory_size=2048,
        )

        generate_answer_lambda = lambda_python.PythonFunction(
            self,
            "GenerateAnswerAgent",
            entry="functions/ai_search/generate_answer",
            runtime=lambda_.Runtime.PYTHON_3_12,
            timeout=Duration.seconds(60),
            memory_size=1024,
            role=lambda_role,
        )

        understand_user_question_task = tasks.LambdaInvoke(
            self,
            "Understand User Question",
            lambda_function=understand_user_question_lambda,
            result_selector={"keywords": sfn.JsonPath.list_at("$.Payload")},
            result_path="$.output_keywords",
            retry_on_service_exceptions=True,
        )

        query_search_engine_task = tasks.LambdaInvoke(
            self,
            "Search The Web",
            lambda_function=query_search_engine_lambda,
            input_path="$.output_keywords",
            result_selector={"results": sfn.JsonPath.object_at("$.Payload")},
            result_path="$.output_search_results",
        )

        scrap_web_pages_task = tasks.LambdaInvoke(
            self,
            "Read the Sources",
            lambda_function=scrap_web_pages_lambda,
            input_path="$.output_search_results",
            result_selector={"sources": sfn.JsonPath.object_at("$.Payload")},
            result_path="$.output_sources",
        )

        generate_answer_task = tasks.LambdaInvoke(
            self,
            "Generate Answer",
            lambda_function=generate_answer_lambda,
            result_selector={"answer": sfn.JsonPath.object_at("$.Payload")},
            # result_path="$.output_answers",
        )

        workflow = (
            understand_user_question_task.next(query_search_engine_task)
            .next(scrap_web_pages_task)
            .next(generate_answer_task)
        )

        sfn.StateMachine(
            self,
            "AI_Search",
            state_machine_name="PromptChainDemo-AISearch",
            definition_body=sfn.DefinitionBody.from_chainable(workflow),
            timeout=Duration.seconds(300),
        )
