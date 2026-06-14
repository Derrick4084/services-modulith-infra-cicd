#!/usr/bin/env python3
import os

import aws_cdk as cdk
from aws_cdk import (
    Aws
)

from ecomm_pipeline.ecomm_pipeline_stack import EcommPipelineStack


config = {
    "development_branch": "develop",
    "production_branch": "main",
    "github": {
       "connection_arn": f"arn:aws:codeconnections:{Aws.REGION}:{Aws.ACCOUNT_ID}:connection/0bfbfa62-024e-4b11-a838-f1035051dad0",
       "owner": "Derrick4084",
       "repo": "aws-kubernetes"      
    },
    "bucketname": f"codepipeline-assets-{Aws.ACCOUNT_ID}",
    "pipelinename": "EcommPipeline",
    "sns":{
        "topic": "ecomm-pipeline",
        "emails": ["admin@example.com"],
    },   
}



app = cdk.App()

EcommPipelineStack(app, "DevelopmentPipeline",
    development_pipeline=True, 
    config=config,
    env={
        "account": Aws.ACCOUNT_ID,
        "region": Aws.REGION,
    }
)

EcommPipelineStack(app, "ProductionPipeline",
    development_pipeline=False, 
    config=config,
    env={
        "account": Aws.ACCOUNT_ID,
        "region": Aws.REGION,
    }
)




app.synth()
