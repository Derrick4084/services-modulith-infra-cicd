from aws_cdk import (
    Aws,
    Stack,
    RemovalPolicy,
    aws_s3 as s3,
    aws_sns as sns,
    aws_kms as kms,
    aws_iam as iam_,
    # aws_codebuild as codebuild,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as codepipeline_actions,
    # aws_codestarnotifications as notifications,
    CfnCapabilities, 
)
from constructs import Construct
from ecomm_pipeline.pipeline_helper import ( 
    get_build_spec, 
    get_codebuild_action,
    get_stack_action,
    create_topic,
    get_notification,
    create_subscription
)

from typing import List
import json

class EcommPipelineStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, development_pipeline: bool, config: dict = None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        owner = config["github"]["owner"]
        repo = config["github"]["repo"]
        repo_conn = config["github"]["connection_arn"]
        # dev_branch = config["development_branch"]
        # prod_branch = config["production_branch"]
        bucketname = config["bucketname"]
        # pipelinename = config["pipelinename"]
        # stage = config["stage"]["dev"]
        sns_topic = config["sns"]["topic"]
        sns_emails = config["sns"]["emails"]

        # env_config = {
        #     "dev": {
        #         "stage": "dev",
        #         "branch": config["development_branch"],
        #         "pipeline_name": f"{config['pipelinename']}-dev",
        #         "approval_required": False,
        #     },
        #     "prod": {
        #         "stage": "prod",
        #         "branch": config["production_branch"],
        #         "pipeline_name": f"{config['pipelinename']}-prod",
        #         "approval_required": True,
        #     }
        # }[environment]

        if development_pipeline:
            env_config = {
                "branch": config["development_branch"],
                "stage": "dev",
                "pipeline_name": f"{config['pipelinename']}-dev",
                "require_approval": False,
                "stack_name": "dev-EcsFargateStack",
                "auto_destroy": True
            }
        else:
            env_config = {
                "branch": config["production_branch"],
                "stage": "prod",
                "pipeline_name": f"{config['pipelinename']}-prod",
                "require_approval": True,
                "stack_name": "prod-EcsFargateStack",
                "auto_destroy": False
            }



        action_role = iam_.Role(
            self, "EcommPipelineActionRole",
            assumed_by=iam_.CompositePrincipal(
                iam_.ServicePrincipal("codepipeline.amazonaws.com"),
                iam_.ServicePrincipal("codebuild.amazonaws.com"),
                iam_.ServicePrincipal("cloudformation.amazonaws.com")    
            ),
            role_name="EcommPipelineActionRole"
        )
        action_role.add_to_policy(iam_.PolicyStatement(
            sid="CodepipelineUseConnRolePolicy",
            effect=iam_.Effect.ALLOW,
            actions=[
                "codeconnections:UseConnection",
                "codestar-connections:UseConnection",
            ],
            resources=[
                f"need to be replaced with the actual connection ARN"
            ]
        ))
        action_role.add_to_policy(iam_.PolicyStatement(
            sid="CodepipelineGitPullRolePolicy",
            effect=iam_.Effect.ALLOW,
            actions=[
                "codecommit:GitPull",
            ],
            resources=["*"]
        ))

        # Pipeline bucket encrytion/decription key
        kms_key = kms.Key(self, "KMSKey",
            removal_policy=RemovalPolicy.DESTROY,
        )
        kms_key.grant_encrypt_decrypt(action_role)


        # Create sns topic for notifications
        topic = create_topic(self, sns_topic, action_role)

        

        # Pipeline build output artifacts locations
        build_output = codepipeline.Artifact(artifact_name="build")
        source = codepipeline.Artifact(artifact_name="source")


        fargate_template_output = codepipeline.Artifact(artifact_name="fargate-template")
        postgres_template_output = codepipeline.Artifact(artifact_name="postgres-template")
        documentdb_template_output = codepipeline.Artifact(artifact_name="documentdb-template")
        vpc_template_output = codepipeline.Artifact(artifact_name="vpc-template")

        

        # Pipeline arctifact bucket
        pipeline_artifact_bucket = s3.Bucket(self, "PipelineBucket",
            encryption_key=kms_key,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            bucket_name=bucketname
        )
        pipeline_artifact_bucket.grant_read_write(action_role)



        # Connection to Github repository
        source_action = codepipeline_actions.CodeStarConnectionsSourceAction(
            action_name="Source",
            owner=owner,
            repo=repo,
            output=source,
            connection_arn=repo_conn,
            branch=env_config["branch"],
            trigger_on_push=True,
            run_order=1
        )

        # CDK build project
        build_cdk = get_build_spec(
            self,
            name="CDK_Build",
            role=action_role,
            commands=["cdk synth"],
            dir=".",
            files=["**/*"],
            kms_key=kms_key
        )


        # Fargate build project
        fargate_template = get_build_spec(
            self,
            name="EcsFargateStackSynth",
            role=action_role,
            commands=["cdk synth EcsFargateStack -o dist"],
            dir="dist",
            files=["EcsFargateStack.template.json"],
            kms_key=kms_key
        )
        # Postgres build project
        postgres_template = get_build_spec(
            self,
            name="PostgresDBStackSynth",
            role=action_role,
            commands=["cdk synth PostgresDBStack -o dist"],
            dir="dist",
            files=["PostgresDBStack.template.json"],
            kms_key=kms_key
        )
        # DocumentDB build project
        documentdb_template = get_build_spec(
            self,
            name="DocumentDBStackSynth",
            role=action_role,
            commands=["cdk synth DocumentDBStack -o dist"],
            dir="dist",
            files=["DocumentDBStack.template.json"],
            kms_key=kms_key
        )
        # VPC build project
        vpc_template = get_build_spec(
            self,
            name="VPCStackSynth",
            role=action_role,
            commands=["cdk synth VpcStack -o dist"],
            dir="dist",
            files=["VpcStack.template.json"],
            kms_key=kms_key
        )

    

        # Cdk codebuild actions
        build_cdk_action = get_codebuild_action(
            name="Building_CDK",
            role=action_role,
            project=build_cdk,
            artifact=build_output,
            source=source,
            run_order=2
        )
        # Fargate codebuild action
        fargate_template_action = get_codebuild_action(
            name="Building_Fargate_Template",
            role=action_role,
            project=fargate_template,
            artifact=fargate_template_output,
            source=build_output,
            run_order=3
        )
        # Postgres codebuild action
        postgres_template_action = get_codebuild_action(
            name="Building_Postgres_Template",
            role=action_role,
            project=postgres_template,
            artifact=postgres_template_output,
            source=build_output,
            run_order=3
        )
        # DocumentDB codebuild action
        documentdb_template_action = get_codebuild_action(
            name="Building_DocumentDB_Template",
            role=action_role,
            project=documentdb_template,
            artifact=documentdb_template_output,
            source=build_output,
            run_order=3
        )
        # VPC codebuild action
        vpc_template_action = get_codebuild_action(
            name="Building_VPC_Template",
            role=action_role,
            project=vpc_template,
            artifact=vpc_template_output,
            source=build_output,
            run_order=3
        )

        # Approval codebuild action
        approval_action = codepipeline_actions.ManualApprovalAction(
            action_name="Approve",
            additional_information="Approve Cloudformation Stack Deployment",
            role=action_role,
            notification_topic=topic,
            notify_emails=sns_emails,
            run_order=4
        )


        # VpcStack deployment actions
        vpc_stack_action = get_stack_action(
            name="DeployVPCStack",
            role=action_role,
            stack_name="VpcStack",
            template_path=vpc_template_output.at_path("VpcStack.template.json"),
            run_order=5
        )
        # PostgresDBStack deployment actions
        postgres_stack_action = get_stack_action(
            name="DeployPostgresStack",
            role=action_role,
            stack_name="PostgresDBStack",
            template_path=postgres_template_output.at_path("PostgresDBStack.template.json"),
            run_order=6
        )
        # DocumentDBStack deployment actions
        documentdb_stack_action = get_stack_action(
            name="DeployDocumentDBStack",
            role=action_role,
            stack_name="DocumentDBStack",
            template_path=documentdb_template_output.at_path("DocumentDBStack.template.json"),
            run_order=6
        )
        # FargateStack deployment actions
        fargate_stack_action = get_stack_action(
            name="DeployFargateStack",
            role=action_role,
            stack_name="EcsFargateStack",
            template_path=fargate_template_output.at_path("EcsFargateStack.template.json"),
            run_order=7
        )


        # Create pipeline     
        pipeline = codepipeline.Pipeline(self, "Pipeline",
              pipeline_type=codepipeline.PipelineType.V2,
              pipeline_name = env_config["pipeline_name"],
              role=action_role,
              artifact_bucket=pipeline_artifact_bucket,
              cross_account_keys=False
            )        
        pipeline.add_stage(
            stage_name="Source",
            actions=[source_action]
        )
        pipeline.add_stage(
            stage_name="Build",
            actions=[build_cdk_action, fargate_template_action, postgres_template_action, documentdb_template_action, vpc_template_action]
        )
        if env_config["require_approval"]:
            pipeline.add_stage(
                stage_name="Approve",
                actions=[approval_action]
        )
        pipeline.add_stage(
            stage_name="Deploy",
            actions=[vpc_stack_action, postgres_stack_action, documentdb_stack_action, fargate_stack_action]
        )

        pipeline.add_to_role_policy(iam_.PolicyStatement(
            effect=iam_.Effect.ALLOW,
            resources=[action_role.role_arn],
            actions=["sts:AssumeRole"]
        ))


        # Create the notifications
        build_notices = get_notification(self, "Build", build_cdk, topic)
        fargate_template_notices = get_notification(self, "FargateTemplate", fargate_template, topic)
        postgres_template_notices = get_notification(self, "PostgresTemplate", postgres_template, topic)
        documentdb_template_notices = get_notification(self, "DocumentDBTemplate", documentdb_template, topic)
        vpc_template_notices = get_notification(self, "VpcTemplate", vpc_template, topic)


        # Create SNS email subscriptions if emails are provided
        if sns_emails:
            # Create subscriptions 
            for email in sns_emails:
                create_subscription(self,email, topic)