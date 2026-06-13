import aws_cdk as core
import aws_cdk.assertions as assertions

from ecomm_pipeline.ecomm_pipeline_stack import EcommPipelineStack

# example tests. To run these tests, uncomment this file along with the example
# resource in ecomm_pipeline/ecomm_pipeline_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = EcommPipelineStack(app, "ecomm-pipeline")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
