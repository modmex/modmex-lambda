



class CORSConfig:

    _REQUIRED_HEADERS = ["Authorization", "Content-Type", "X-Amz-Date", "X-Api-Key", "X-Amz-Security-Token"]

    def __init__(
        self,
        allow_origin: str = "*",
        extra_origins: list[str] | None = None,
        allow_headers: list[str] | None = None,
        expose_headers: list[str] | None = None,
        max_age: int | None = None,
        allow_credentials: bool = False,
    ):
        """
        Parameters
        ----------
        allow_origin: str
            The value of the `Access-Control-Allow-Origin` to send in the response. Defaults to "*", but should
            only be used during development.
        extra_origins: list[str] | None
            The list of additional allowed origins.
        allow_headers: list[str] | None
            The list of additional allowed headers. This list is added to list of
            built-in allowed headers: `Authorization`, `Content-Type`, `X-Amz-Date`,
            `X-Api-Key`, `X-Amz-Security-Token`.
        expose_headers: list[str] | None
            A list of values to return for the Access-Control-Expose-Headers
        max_age: int | None
            The value for the `Access-Control-Max-Age`
        allow_credentials: bool
            A boolean value that sets the value of `Access-Control-Allow-Credentials`
        """

        self._allowed_origins = [allow_origin]

        if extra_origins:
            self._allowed_origins.extend(extra_origins)

        self.allow_headers = set(self._REQUIRED_HEADERS + (allow_headers or []))
        self.expose_headers = expose_headers or []
        self.max_age = max_age
        self.allow_credentials = allow_credentials

    def to_dict(self, origin: str | None) -> dict[str, str]:
        """Builds the configured Access-Control http headers"""

        # If there's no Origin, don't add any CORS headers
        if not origin:
            return {}

        # If the origin doesn't match any of the allowed origins, and we don't allow all origins ("*"),
        # don't add any CORS headers
        if origin not in self._allowed_origins and "*" not in self._allowed_origins:
            return {}

        # The origin matched an allowed origin, so return the CORS headers
        headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Headers": CORSConfig.build_allow_methods(self.allow_headers),
        }

        if self.expose_headers:
            headers["Access-Control-Expose-Headers"] = ",".join(self.expose_headers)
        if self.max_age is not None:
            headers["Access-Control-Max-Age"] = str(self.max_age)
        if origin != "*" and self.allow_credentials is True:
            headers["Access-Control-Allow-Credentials"] = "true"
        return headers

    def allowed_origin(self, extracted_origin: str) -> str | None:
        if extracted_origin in self._allowed_origins:
            return extracted_origin
        if extracted_origin is not None and "*" in self._allowed_origins:
            return "*"

        return None

    @staticmethod
    def build_allow_methods(methods: set[str]) -> str:
        """Build sorted comma delimited methods for Access-Control-Allow-Methods header

        Parameters
        ----------
        methods : set[str]
            Set of HTTP Methods

        Returns
        -------
        set[str]
            Formatted string with all HTTP Methods allowed for CORS e.g., `GET, OPTIONS`

        """
        return ",".join(sorted(methods))