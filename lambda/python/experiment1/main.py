from matrixMultiplication import multiply_matrix


def exp1_workloads(event, context):
    multiply_matrix()
    return {"statusCode": 200, "body": "ok"}