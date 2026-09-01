#!/usr/bin/env python3
import os

import aws_cdk as cdk
from aws_cdk import (
    Aws
)

from ecomm_pipeline.ecomm_pipeline_stack import EcommPipelineStack


config = {
    "development_branch": "dev",
    "production_branch": "main",
    "github": {
       "connection_arn": f"arn:aws:codeconnections:{Aws.REGION}:{Aws.ACCOUNT_ID}:connection/2ab05b27-1bfc-4e70-be99-6160eaaa529a",
       "owner": "Derrick4084",
       "repo": "services-modulith-infra-cdk",
       "domain": "token.actions.githubusercontent.com"     
    },
    "bucketname": f"codepipeline-assets-{Aws.ACCOUNT_ID}",
    "pipelinename": "EcommPipeline",
    "sns":{
        "topic": "ecomm-pipeline",
        "emails": ["admin@example.com"],
    }  
}



app = cdk.App()

EcommPipelineStack(app, "DevelopmentPipeline",
    development_pipeline=True,
    environment="dev",
    config=config,
    env={
        "account": Aws.ACCOUNT_ID,
        "region": Aws.REGION,
    }
)

EcommPipelineStack(app, "ProductionPipeline",
    development_pipeline=False,
    environment="prod",
    config=config,
    env={
        "account": Aws.ACCOUNT_ID,
        "region": Aws.REGION,
    }
)


app.synth()
