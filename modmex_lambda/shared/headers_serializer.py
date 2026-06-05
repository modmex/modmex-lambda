from __future__ import annotations


from abc import ABC, abstractmethod
from collections import defaultdict
from typing import  Any
from modmex_lambda.shared.cookies import Cookie


class BaseHeadersSerializer(ABC):

    @abstractmethod
    def serialize(self, headers: dict[str, str | list[str]], cookies: list[Cookie]) -> dict[str, Any]:
        raise NotImplementedError()


class HttpApiHeadersSerializer(BaseHeadersSerializer):
    def serialize(self, headers: dict[str, str | list[str]], cookies: list[Cookie]) -> dict[str, Any]:
        """
        When using HTTP APIs or LambdaFunctionURLs, everything is taken care automatically for us.
        We can directly assign a list of cookies and a dict of headers to the response payload, and the
        runtime will automatically serialize them correctly on the output.
        """

        # Format 2.0 doesn't have multiValueHeaders or multiValueQueryStringParameters fields.
        # Duplicate headers are combined with commas and included in the headers field.
        combined_headers: dict[str, str] = {}
        for key, values in headers.items():
            # omit headers with explicit null values
            if values is None:
                continue

            if isinstance(values, str):
                combined_headers[key] = values
            else:
                combined_headers[key] = ", ".join(values)

        return {"headers": combined_headers, "cookies": list(map(str, cookies))}


class MultiValueHeadersSerializer(BaseHeadersSerializer):
    def serialize(self, headers: dict[str, str | list[str]], cookies: list[Cookie]) -> dict[str, Any]:
        """
        When using REST APIs, headers can be encoded using the `multiValueHeaders` key on the response.
        This is also the case when using an ALB integration with the `multiValueHeaders` option enabled.
        The solution covers headers with just one key or multiple keys.
        """
        payload: dict[str, list[str]] = defaultdict(list)
        for key, values in headers.items():
            # omit headers with explicit null values
            if values is None:
                continue

            if isinstance(values, str):
                payload[key].append(values)
            else:
                payload[key].extend(values)

        if cookies:
            payload.setdefault("Set-Cookie", [])
            for cookie in cookies:
                payload["Set-Cookie"].append(str(cookie))

        return {"multiValueHeaders": payload}

