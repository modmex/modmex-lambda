from functools import reduce


def update_expression(item: dict):
    keys = item.keys()
    result = {}
    result['ExpressionAttributeNames'] = reduce(
        lambda accumulator, el: {**accumulator, **el},
        map(
            lambda attrName: {f"#{attrName}": attrName },
            keys
        ),
        {}
    )
    result['ExpressionAttributeValues'] = reduce(
        lambda accumulator, el: {**accumulator, **el},
        map(
            lambda attrName: {f":{attrName}": item[attrName] },
            filter(
                lambda attrName: item[attrName] is not None,
                keys
            )
        ),
        {}
    )
    result['UpdateExpression'] = "SET "+", ".join(map(
            lambda attrName: f"#{attrName} = :{attrName}",
            filter(
                lambda attrName: item[attrName] is not None,
                keys
            )
        ))
    update_expression_remove = ", ".join(map(
            lambda attrName: f"#{attrName}",
            filter(
                lambda attrName: item[attrName] is None,
                keys
            )
        ))
    if update_expression_remove:
        result['UpdateExpression'] = "{} REMOVE {}".format(
            result['UpdateExpression'],
            update_expression_remove
        )
    result['ReturnValues'] = 'ALL_NEW'
    return result


def timestamp_condition(field_name = 'timestamp'):
    return {
        'ConditionExpression': "attribute_not_exists(#{fn}) OR #{fn} < :{fn}".format(
            fn=field_name
        )
    }


def pk_condition(field_name = 'pk'):
    return {
        'ConditionExpression': "attribute_not_exists({})".format(
            field_name
        )
    }
