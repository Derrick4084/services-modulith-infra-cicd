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
    get_deploy_action,
    create_topic,
    get_notification,
    create_subscription
)

from typing import List
import json

class EcommPipelineStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, 
                 development_pipeline: bool, 
                 config: dict = None,
                 environment: str = "prod", 
                 **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        owner = config["github"]["owner"]
        repo = config["github"]["repo"]
        repo_conn = config["github"]["connection_arn"]
        bucketname = config["bucketname"]
        sns_topic = config["sns"]["topic"]
        sns_emails = config["sns"]["emails"]
        github_domain = config["github"]["domain"]

        self.env_name = environment

        
        if development_pipeline:
            env_config = {
                "branch": config["development_branch"],
                "stage": "dev",
                "pipeline_name": f"{config['pipelinename']}-dev",
                "require_approval": False,
                "stack_name": "dev-EcommAppPipelineStack",
                "auto_destroy": True
            }
        else:
            env_config = {
                "branch": config["production_branch"],
                "stage": "prod",
                "pipeline_name": f"{config['pipelinename']}-prod",
                "require_approval": True,
                "stack_name": "prod-EcommAppPipelineStack",
                "auto_destroy": False
            }

           
        

    
        oidc_provider = iam_.OpenIdConnectProvider(self, "OidcProvider",
            url=f"https://{github_domain}",
            client_ids=["sts.amazonaws.com"],
            removal_policy=RemovalPolicy.DESTROY,
            # thumbprints=["AB9D0263244DD0326EB67015705A667E79CFE998"]
        )
        github_action_role = iam_.Role(self, "GitHubActionsDeploymentRole",
            assumed_by=iam_.FederatedPrincipal(
                federated=oidc_provider.open_id_connect_provider_arn,
                actions=["sts:AssumeRoleWithWebIdentity"],
                conditions={
                    "StringEquals": {
                        f"{github_domain}:aud": "sts.amazonaws.com"
                    },
                    "StringLike": {
                        # Restricts role assumption strictly to your repo on specific branches
                        f"{github_domain}:sub": [
                            f"repo:{owner}/{repo}:ref:refs/heads/main",
                            f"repo:{owner}/{repo}:ref:refs/heads/dev"
                        ]
                    }
                }
            )
        )
        github_action_role.add_to_policy(iam_.PolicyStatement(
            sid="GitHubActionsDeploymentPolicy",
            effect=iam_.Effect.ALLOW,
            actions=[
                "codedeploy:CreateDeployment",
                "codedeploy:BatchGetBuilds",
                "cloudformation:CreateStack",
                "cloudformation:UpdateStack",
                "cloudformation:DeleteStack",
                "cloudformation:DescribeStacks",
                "cloudformation:DescribeStackEvents",
                "cloudformation:SetStackPolicy",
                "cloudformation:ValidateTemplate"
            ],
            resources=["*"]
        ))


        build_role = iam_.Role(self, f"{self.env_name}-EcommPipelineBuildRole",
            assumed_by=iam_.ServicePrincipal(
                "codebuild.amazonaws.com"
            ),
            role_name=f"{self.env_name}-EcommPipelineBuildRole"
        )
        build_role.add_to_policy(iam_.PolicyStatement(
            sid="CodebuildRolePolicy",
            effect=iam_.Effect.ALLOW,
            actions=[
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
                "codebuild:CreateReportGroup",
                "codebuild:CreateReport",
                "codebuild:BatchPutTestCases",
                "codebuild:BatchPutCodeCoverages",
                "codebuild:UpdateReport",
                "codebuild:BatchGetBuilds",
                "codebuild:StartBuild"
            ],
            resources=["*"]
        ))


        # Pipeline build output artifacts locations
        build_output = codepipeline.Artifact(artifact_name="build")
        source = codepipeline.Artifact(artifact_name="source")


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
            role=build_role,
            commands=["cdk synth"],
            dir="cdk.out",
            files=["**/*"],
            kms_key=kms_key,
            env=self.env_name
        )


        # Cdk codebuild actions
        build_cdk_action = get_codebuild_action(
            name="Building_CDK",
            role=build_role,
            project=build_cdk,
            artifact=build_output,
            source=source,
            run_order=2
        )
        
        
        # Approval codebuild action
        approval_action = codepipeline_actions.ManualApprovalAction(
            action_name="Approve",
            additional_information="Approve Cloudformation Stack Deployment",
            role=build_role,
            notification_topic=topic,
            notify_emails=sns_emails,
            run_order=3
        )


        # Deployment role for cloudformation
        deployment_role = iam_.Role(self, f"{self.env_name}-CloudFormationDeploymentRole",
            assumed_by=iam_.ServicePrincipal(
                "cloudformation.amazonaws.com"
            ),
            role_name=f"{self.env_name}-CloudFormationDeploymentRole",
        )
        deployment_role.add_to_policy(iam_.PolicyStatement(
            sid="CodepipelineUseConnRolePolicy",
            effect=iam_.Effect.ALLOW,
            actions=[
                "codeconnections:UseConnection",
                "codestar-connections:UseConnection",
            ],
            resources=[
                repo_conn
            ]
        ))
        deployment_role.add_to_policy(iam_.PolicyStatement(
            sid="CloudFormationAction",
            effect=iam_.Effect.ALLOW,
            actions=[
                "s3:GetObject",
                "s3:PutObject",
                "s3:GetObjectVersion",
                "cloudformation:CreateStack",
                "cloudformation:UpdateStack",
                "cloudformation:DeleteStack",
                "cloudformation:DescribeStacks",
                "cloudformation:DescribeStackEvents",
                "cloudformation:SetStackPolicy",
                "cloudformation:ValidateTemplate",
            ],
            resources=["*"],
            )
        )
        
        # VpcStack deployment actions
        vpc_stack_action = get_deploy_action(
            name=f"{self.env_name}-DeployVPCStack",
            role=deployment_role,
            stack_name=f"{self.env_name}-VpcStack",
            template_path=build_output.at_path("VpcStack.template.json"),
            run_order=4
        )

        # AiModelStack deployment actions
        model_stack_action = get_deploy_action(
            name=f"{self.env_name}-DeployModelStack",
            role=deployment_role,
            stack_name=f"{self.env_name}-AiModelStack",
            template_path=build_output.at_path("AiModelStack.template.json"),
            run_order=5
        )

        # QdrantStack deployment actions
        qdrant_stack_action = get_deploy_action(
            name=f"{self.env_name}-QdrantStack",
            role=deployment_role,
            stack_name=f"{self.env_name}-QdrantStack",
            template_path=build_output.at_path("QdrantStack.template.json"),
            run_order=5
        )

        # RedisClusterStack deployment actions
        redis_stack_action = get_deploy_action(
            name=f"{self.env_name}-RedisClusterStack",
            role=deployment_role,
            stack_name=f"{self.env_name}-RedisClusterStack",
            template_path=build_output.at_path("RedisClusterStack.template.json"),
            run_order=5
        )

        # ZipkinStack deployment actions
        zipkin_stack_action = get_deploy_action(
            name=f"{self.env_name}-ZipkinStack",
            role=deployment_role,
            stack_name=f"{self.env_name}-ZipkinStack",
            template_path=build_output.at_path("ZipkinStack.template.json"),
            run_order=5
        )

        # PostgresDBStack deployment actions
        postgres_stack_action = get_deploy_action(
            name=f"{self.env_name}-DeployPostgresStack",
            role=deployment_role,
            stack_name=f"{self.env_name}-PostgresDBStack",
            template_path=build_output.at_path("PostgresDBStack.template.json"),
            run_order=5
        )

        # DocumentDBStack deployment actions
        documentdb_stack_action = get_deploy_action(
            name=f"{self.env_name}-DeployDocumentDBStack",
            role=deployment_role,
            stack_name=f"{self.env_name}-DocumentDBStack",
            template_path=build_output.at_path("DocumentDBStack.template.json"),
            run_order=5
        )

        # PostgresConfigStack deployment actions
        postgres_config_stack_action = get_deploy_action(
            name=f"{self.env_name}-DeployPostgresConfigStack",
            role=deployment_role,
            stack_name=f"{self.env_name}-PostgresConfigStack",
            template_path=build_output.at_path("PostgresConfigStack.template.json"),
            run_order=6
        )

        # RedisInsightStack deployment actions
        redis_insight_stack_action = get_deploy_action(
            name=f"{self.env_name}-DeployRedisInsightStack",
            role=deployment_role,
            stack_name=f"{self.env_name}-RedisInsightStack",
            template_path=build_output.at_path("RedisInsightStack.template.json"),
            run_order=6
        )

        # FargateStack deployment actions
        fargate_stack_action = get_deploy_action(
            name=f"{self.env_name}-DeployEcsFargateStack",
            role=deployment_role,
            stack_name=f"{self.env_name}-EcsFargateStack",
            template_path=build_output.at_path("EcsFargateStack.template.json"),
            run_order=7
        )


        pipeline_role = iam_.Role(self, f"{self.env_name}-EcommPipelineRole",
            assumed_by=iam_.ServicePrincipal(
                "codepipeline.amazonaws.com"
            ),
            role_name=f"{self.env_name}-EcommPipelineActionRole"
        )
        pipeline_role.add_to_policy(iam_.PolicyStatement(
            sid="CodepipelineUseConnRolePolicy",
            effect=iam_.Effect.ALLOW,
            actions=[
                "codeconnections:UseConnection",
                "codestar-connections:UseConnection",
            ],
            resources=[
                repo_conn
            ]
        ))
        pipeline_role.add_to_policy(iam_.PolicyStatement(
            sid="CodepipelineResourcesRolePolicy",
            effect=iam_.Effect.ALLOW,
            actions=[
                "s3:GetObject",
                "s3:PutObject",
                "s3:GetBucketAcl",
                "s3:GetObjectVersion",
                "codebuild:StartBuild",
                "codebuild:BatchGetBuilds",
                "codedeploy:CreateDeployment",
                "codedeploy:BatchGetBuilds",
                "cloudformation:CreateStack",
                "cloudformation:UpdateStack",
                "cloudformation:DescribeStacks",
                "cloudformation:DescribeStackEvents",
                "cloudformation:SetStackPolicy",
                "iam:PassRole",
                "kms:Encrypt",
                "kms:Decrypt",
                "sns:CreateTopic",
                "sns:Subscribe",
                "sns:Publish"
            ],
            resources=["*"]
        ))

        # Pipeline arctifact bucket
        pipeline_artifact_bucket = s3.Bucket(self, f"{self.env_name}-PipelineBucket",
            encryption_key=kms_key,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            bucket_name=bucketname
        )
        pipeline_artifact_bucket.grant_read_write(pipeline_role)


        # Pipeline bucket encrytion/decription key
        kms_key = kms.Key(self, f"{self.env_name}-KMSKey",
            removal_policy=RemovalPolicy.DESTROY,
        )
        kms_key.grant_encrypt_decrypt(pipeline_role)


        # Create sns topic for notifications
        topic = create_topic(self, sns_topic, pipeline_role)








        # Create pipeline     
        pipeline = codepipeline.Pipeline(self, f"{self.env_name}-Pipeline",
              pipeline_type=codepipeline.PipelineType.V2,
              pipeline_name = env_config["pipeline_name"],
              role=pipeline_role,
              artifact_bucket=pipeline_artifact_bucket,
              cross_account_keys=False
            )        
        pipeline.add_stage(
            stage_name=f"{self.env_name}-Source",
            actions=[source_action]
        )
        pipeline.add_stage(
            stage_name=f"{self.env_name}-Build",
            actions=[build_cdk_action]
        )
        if env_config["require_approval"]:
            pipeline.add_stage(
                stage_name="Approve",
                actions=[approval_action]
        )

        deploy_actions = [
                vpc_stack_action,
                model_stack_action,
                qdrant_stack_action,
                redis_stack_action,
                zipkin_stack_action,
                documentdb_stack_action,
                postgres_stack_action,  
                postgres_config_stack_action,       
                fargate_stack_action
            ]

        if self.env_name == "dev":
            deploy_actions.insert(8, redis_insight_stack_action)
            
        pipeline.add_stage(
            stage_name=f"{self.env_name}-Deploy",
            actions=deploy_actions
        )

        
        # Create the notifications
        build_notices = get_notification(self, "Build", build_cdk, topic)
        

        # Create SNS email subscriptions if emails are provided
        if sns_emails:
            # Create subscriptions 
            for email in sns_emails:
                create_subscription(self,email, topic)