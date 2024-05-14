from aws_cdk import (
    Duration,
    Stack,
    RemovalPolicy,
    aws_certificatemanager as acm,
    aws_cognito as cognito,
    aws_ec2 as ec2,
    aws_ecr_assets as ecr_assets,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_elasticloadbalancingv2 as elb,
    aws_elasticloadbalancingv2_actions as elb_actions,
    aws_route53 as route53,
    aws_secretsmanager as secretsmanager,
    aws_stepfunctions as sfn,
)
from constructs import Construct


class WebappStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, parent_domain: str, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Set up load-balanced HTTPS Fargate service
        vpc = ec2.Vpc(
            self,
            "VPC",
            max_azs=2,
        )

        cluster = ecs.Cluster(self, "Cluster", vpc=vpc)

        image = ecs.ContainerImage.from_asset(
            "webapp", platform=ecr_assets.Platform.LINUX_AMD64
        )

        fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "StreamlitService",
            cluster=cluster,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=image, container_port=8501  # 8501 is the default Streamlit port
            ),
            public_load_balancer=True,
        )

        # Configure Streamlit's health check
        fargate_service.target_group.configure_health_check(
            enabled=True, path="/_stcore/health", healthy_http_codes="200"
        )

        # Speed up deployments
        fargate_service.target_group.set_attribute(
            key="deregistration_delay.timeout_seconds",
            value="10",
        )

        # Grant access to start and query Step Functions exections
        for name_suffix in [
            "BlogPost",
            "TripPlanner",
            "StoryWriter",
            "MoviePitch",
            "MealPlanner",
            "MostPopularRepoBedrockAgents",
            "MostPopularRepoLangchain",
            "AISearch",
        ]:
            workflow = sfn.StateMachine.from_state_machine_name(
                self, f"{name_suffix}Workflow", f"PromptChainDemo-{name_suffix}"
            )
            workflow.grant_read(fargate_service.task_definition.task_role)
            workflow.grant_start_execution(fargate_service.task_definition.task_role)
            workflow.grant_task_response(fargate_service.task_definition.task_role)
