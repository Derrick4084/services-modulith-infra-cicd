from aws_cdk import (
    Aws,
    Stack,
    RemovalPolicy,
    aws_s3 as s3,
    aws_sns as sns,
    aws_kms as kms,
    aws_iam as iam_,
    aws_codebuild as codebuild,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as codepipeline_actions,
    aws_codestarnotifications as notifications,
    CfnCapabilities, 
)
from constructs import Construct

from typing import List
import json

def get_build_spec(self, name: str, role: iam_.Role, commands: List[str], dir: str, files: List[str], kms_key: kms.Key):
            return codebuild.PipelineProject(
                self, name,
                environment=codebuild.BuildEnvironment(
                    build_image=codebuild.LinuxBuildImage.STANDARD_7_0
                ),
                role=role,
                project_name=name,
                encryption_key=kms_key,
                build_spec=codebuild.BuildSpec.from_object(
                    {
                        "version": "0.2",
                        "phases": {
                            "install": {
                                "commands":["npm install -g aws-cdk@latest",
                                        "python -m pip install -r requirements.txt"]
                            },
                            "build": {
                                "commands": commands
                            }
                        },
                        "artifacts": {
                            "base-directory": dir,
                            "files": files
                        }
                    }
                ),
                
            )

def get_codebuild_action(
                name: str, 
                role: iam_.Role, 
                project: codebuild.PipelineProject, 
                artifact: codepipeline.Artifact, 
                source: codepipeline.Artifact,
                run_order: int = 2,
                extra_outputs: List[codepipeline.Artifact] = None
            ):
            return codepipeline_actions.CodeBuildAction(
                role=role,
                action_name=name,
                project=project,
                input=source,
                outputs=[artifact] + (extra_outputs or []),
                run_order=run_order
            )


def get_stack_action(name: str, role: iam_.Role, stack_name: str, template_path: codepipeline.ArtifactPath, run_order: int = 4):
    return codepipeline_actions.CloudFormationCreateUpdateStackAction(
        action_name=name,
        stack_name=stack_name,
        admin_permissions=True,
        template_path=template_path,
        role=role,
        cfn_capabilities=[CfnCapabilities.NAMED_IAM, CfnCapabilities.AUTO_EXPAND],
        deployment_role=role,
        replace_on_failure=True,
        run_order=run_order,
    )


def create_topic(self, name: str, role: iam_.Role):
            topic = sns.Topic(self, f"SNSTopic{name}",
                topic_name=name
            )
            topic.grant_publish(role)
            topic.apply_removal_policy(RemovalPolicy.DESTROY)
            return topic



def get_notification(self, name: str, project: codebuild.PipelineProject, topic: sns.Topic):
            return notifications.NotificationRule(self, f"NotificationRule{name}",
                source=project,
                events=["codebuild-project-build-state-succeeded",
                        "codebuild-project-build-state-failed"],
                targets=[topic],
                notification_rule_name=name
            )

def create_subscription(self, email: str, topic: sns.Topic):
            name = email.split("@")[0]
            sns.Subscription(self, f"notification-{name}",
                topic=topic,
                endpoint=email,
                protocol=sns.SubscriptionProtocol.EMAIL
            )