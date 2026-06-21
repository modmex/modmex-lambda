from modmex_lambda.persistence.dynamodb.expressions import (
    pk_condition,
    timestamp_condition,
    update_expression,
)


def test_update_expression_builds_set_and_remove_expression() -> None:
    result = update_expression({
        'name': 'Desk',
        'count': 2,
        'deleted': None,
    })

    assert result == {
        'ExpressionAttributeNames': {
            '#name': 'name',
            '#count': 'count',
            '#deleted': 'deleted',
        },
        'ExpressionAttributeValues': {
            ':name': 'Desk',
            ':count': 2,
        },
        'UpdateExpression': 'SET #name = :name, #count = :count REMOVE #deleted',
        'ReturnValues': 'ALL_NEW',
    }


def test_timestamp_condition() -> None:
    assert timestamp_condition() == {
        'ConditionExpression': 'attribute_not_exists(#timestamp) OR #timestamp < :timestamp',
    }


def test_pk_condition() -> None:
    assert pk_condition() == {
        'ConditionExpression': 'attribute_not_exists(pk)',
    }
