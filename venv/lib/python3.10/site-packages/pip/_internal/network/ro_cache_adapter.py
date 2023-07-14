import zlib

from pip._vendor.requests.adapters import HTTPAdapter

from pip._vendor.cachecontrol.controller import CacheController
from pip._vendor.cachecontrol.cache import DictCache
from pip._vendor.cachecontrol.filewrapper import CallbackFileWrapper


class ReadOnlyCacheControlAdapter(HTTPAdapter):
    invalidating_methods = {"PUT", "DELETE"}

    def __init__(
        self,
        cache=None,
        cache_etags=True,
        controller_class=None,
        serializer=None,
        heuristic=None,
        cacheable_methods=None,
        *args,
        **kw
    ):
        super(ReadOnlyCacheControlAdapter, self).__init__(*args, **kw)
        self.cache = DictCache() if cache is None else cache
        self.heuristic = heuristic
        self.cacheable_methods = cacheable_methods or ("GET",)

        controller_factory = controller_class or CacheController
        self.controller = controller_factory(
            self.cache, cache_etags=cache_etags, serializer=serializer
        )

    def send(self, request, cacheable_methods=None, **kw):
        """
        Send a request. Use the request information to see if it
        exists in the cache and cache the response if we need to and can.
        """
        cacheable = cacheable_methods or self.cacheable_methods
        if request.method in cacheable:
            try:
                cached_response = self.controller.cached_request(request)
            except zlib.error:
                cached_response = None
            if cached_response:
                return self.build_response(request, cached_response, from_cache=True)

        resp = super(ReadOnlyCacheControlAdapter, self).send(request, **kw)

        return resp

    def build_response(
        self, request, response, from_cache=False, cacheable_methods=None
    ):
        """
        Build a response by making a request or using the cache.
        """
        
        resp = super(ReadOnlyCacheControlAdapter, self).build_response(request, response)

        # Give the request a from_cache attr to let people use it
        resp.from_cache = from_cache

        return resp

    def close(self):
        self.cache.close()
        super(ReadOnlyCacheControlAdapter, self).close()
