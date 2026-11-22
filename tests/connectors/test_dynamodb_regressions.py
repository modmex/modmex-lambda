from boto3.dynamodb.types import TypeSerializer

from modmex_lambda.connectors.dynamodb import Connector

_serializer = TypeSerializer()


def _marshall(item):
    return {key: _serializer.serialize(value) for key, value in item.items()}


class PagedClient:
    pages = [[{"pk": "a"}], [{"pk": "b"}], [{"pk": "c"}]]

    def query(self, **kwargs):
        start = kwargs.get("ExclusiveStartKey")
        index = 0 if start is None else int(start["n"]["N"]) + 1
        response = {"Items": [_marshall(item) for item in self.pages[index]]}
        if index < len(self.pages) - 1:
            response["LastEvaluatedKey"] = _marshall({"n": index})
        return response


def test_query_all_does_not_mutate_reused_params():
    connector = Connector(table_name="t", client=PagedClient())
    query = {"KeyConditionExpression": "pk = :p"}  # e.g. a module-level template
    assert [item["pk"] for item in connector.query_all(query)] == ["a", "b", "c"]
    assert [item["pk"] for item in connector.query_all(query)] == ["a", "b", "c"]
    assert query == {"KeyConditionExpression": "pk = :p"}


class BatchClient:
    def __init__(self):
        self.sizes = []

    def batch_get_item(self, **kwargs):
        keys = [key for request in kwargs["RequestItems"].values() for key in request["Keys"]]
        self.sizes.append(len(keys))
        assert len(keys) <= 100, "DynamoDB rejects more than 100 keys"
        return {
            "Responses": {table: request["Keys"] for table, request in kwargs["RequestItems"].items()},
            "UnprocessedKeys": {},
        }


def test_batch_get_splits_requests_over_100_keys():
    client = BatchClient()
    connector = Connector(table_name="t", client=client)
    keys = [{"pk": f"k{i}"} for i in range(150)]
    result = connector.batch_get({"RequestItems": {"t": {"Keys": keys, "ConsistentRead": True}}})
    assert client.sizes == [100, 50]
    assert sorted(item["pk"] for item in result["Responses"]["t"]) == sorted(f"k{i}" for i in range(150))
