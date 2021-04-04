import uuid
from datetime import date

import pytest
from sanic_routing import BaseRouter
from sanic_routing.exceptions import NoMethod, NotFound, RouteExists


@pytest.fixture
def handler():
    def handler(**kwargs):
        return list(kwargs.values())[0]

    return handler


class Router(BaseRouter):
    def get(self, path, method):
        return self.resolve(path=path, method=method)


def test_add_route():
    router = Router()
    router.add("/foo/bar", lambda *args, **kwargs: ...)

    assert len(router.static_routes) == 1

    route = list(router.static_routes.values())[0]
    assert route.parts == ("foo", "bar")


def test_alternatice_delimiter():
    router = Router(delimiter=":")
    router.add("foo:bar", lambda *args, **kwargs: ...)

    assert len(router.static_routes) == 1

    route = list(router.static_routes.values())[0]
    assert route.parts == ("foo", "bar")


def test_add_duplicate_route_fails():
    router = Router()

    router.add("/foo/bar", lambda *args, **kwargs: ...)
    with pytest.raises(RouteExists):
        router.add("/foo/bar", lambda *args, **kwargs: ...)
    router.add("/foo/bar", lambda *args, **kwargs: ..., overwrite=True)

    router.add("/foo/<bar>", lambda *args, **kwargs: ...)
    with pytest.raises(RouteExists):
        router.add("/foo/<bar>", lambda *args, **kwargs: ...)
    router.add("/foo/<bar>", lambda *args, **kwargs: ..., overwrite=True)


def test_add_duplicate_route_alt_method():
    router = Router()
    router.add("/foo/bar", lambda *args, **kwargs: ...)
    router.add("/foo/bar", lambda *args, **kwargs: ..., methods=["ALT"])
    router.add("/foo/<bar>", lambda *args, **kwargs: ...)
    router.add("/foo/<bar:int>", lambda *args, **kwargs: ...)

    assert len(router.static_routes) == 1
    assert len(router.dynamic_routes) == 2

    static_handlers = list(
        list(router.static_routes.values())[0].handlers.values()
    )
    assert len(static_handlers[0]) == 2

    for route in router.dynamic_routes.values():
        assert len(list(route.handlers.values())) == 1
        assert len(list(route.handlers.values())) == 1


def test_route_does_not_exist():
    router = Router()
    router.add("/foo", handler)
    router.finalize()

    with pytest.raises(NotFound):
        router.get("/path/to/nothing", "BASE")


def test_method_does_not_exist():
    router = Router()
    router.add("/foo", handler)
    router.finalize()

    with pytest.raises(NoMethod):
        router.get("/foo", "XXXXXXX")


def test_cast_types_at_same_position(handler):
    router = Router()
    router.add("/foo/<bar>", handler)
    router.add("/foo/<bar:int>", handler)

    router.finalize()

    string_bar = router.get("/foo/something", "BASE")
    int_bar = router.get("/foo/111", "BASE")

    string_retval = string_bar[1](**string_bar[2])
    assert isinstance(string_retval, str)
    assert string_retval == "something"

    int_retval = int_bar[1](**int_bar[2])
    assert isinstance(int_retval, int)
    assert int_retval == 111


@pytest.mark.parametrize(
    "label,value,cast_type",
    (
        ("string", "foo_-", str),
        ("int", 11111, int),
        ("number", 99.99, float),
        ("alpha", "ABCxyz", str),
        ("ymd", "2021-01-01", date),
        ("uuid", uuid.uuid4(), uuid.UUID),
    ),
)
def test_casting(handler, label, value, cast_type):
    router = Router()
    router.add("/<foo:string>", handler)
    router.add("/<foo:int>", handler)
    router.add("/<foo:number>", handler)
    router.add("/<foo:alpha>", handler)
    router.add("/<foo:ymd>", handler)
    router.add("/<foo:uuid>", handler)

    router.finalize()
    _, handler, params = router.get(f"/{value}", "BASE")
    retval = handler(**params)

    assert isinstance(retval, cast_type)


def test_conditional_check_proper_compile(handler):
    router = Router()
    router.add("/<foo>/", handler, strict=True)
    router.add("/<foo>/", handler, strict=True, requirements={"foo": "bar"})
    router.finalize()

    assert router.finalized


@pytest.mark.parametrize(
    "param_name",
    (
        "fooBar",
        "foo_bar",
        "Foobar",
        "foobar1",
    ),
)
def test_use_param_name(handler, param_name):
    router = Router()
    path_part_with_param = f"<{param_name}>"
    router.add(f"/path/{path_part_with_param}", handler)
    route = list(router.routes)[0]
    assert ("path", path_part_with_param) == route


@pytest.mark.parametrize(
    "param_name",
    (
        "fooBar",
        "foo_bar",
        "Foobar",
        "foobar1",
    ),
)
def test_use_param_name_with_casing(handler, param_name):
    router = Router()
    path_part_with_param = f"<{param_name}:str>"
    router.add(f"/path/{path_part_with_param}", handler)
    route = list(router.routes)[0]
    assert ("path", path_part_with_param) == route


def test_use_route_contains_children(handler):
    router = Router()
    router.add("/foo/<foo_id>/bars_ids", handler)
    router.add(
        "/foo/<foo_id>/bars_ids/<bar_id>/settings/<group_id>/groups", handler
    )

    router.finalize()

    bars_ids = router.get("/foo/123/bars_ids", "BASE")
    bars_ids_groups = router.get(
        "/foo/123/bars_ids/321/settings/111/groups", "BASE"
    )

    bars_ids_retval = bars_ids[1](**bars_ids[2])
    assert isinstance(bars_ids_retval, str)
    assert bars_ids_retval == "123"

    bars_ids_group_dict = bars_ids_groups[2]
    assert bars_ids_group_dict == {
        "foo_id": "123",
        "bar_id": "321",
        "group_id": "111",
    }


def test_use_route_with_different_depth(handler):
    router = Router()
    router.add("/foo/<foo_id>", handler)
    router.add("/foo/<foo_id>/settings", handler)
    router.add("/foo/<foo_id>/bars/<bar_id>/settings", handler)
    router.add("/foo/<foo_id>/bars_ids", handler)
    router.add("/foo/<foo_id>/bars_ids/<bar_id>/settings", handler)
    router.add(
        "/foo/<foo_id>/bars_ids/<bar_id>/settings/<group_id>/groups", handler
    )

    router.finalize()

    router.get("/foo/123", "BASE")
    router.get("/foo/123/settings", "BASE")
    router.get("/foo/123/bars/321/settings", "BASE")
    router.get("/foo/123/bars_ids", "BASE")
    router.get("/foo/123/bars_ids/321/settings", "BASE")
    router.get("/foo/123/bars_ids/321/settings/111/groups", "BASE")


def test_use_route_type_coercion(handler):
    router = Router()
    router.add("/test/<foo:int>", handler)
    router.add("/test/<foo:int>/bar", handler)

    router.finalize()

    router.get("/test/123", "BASE")
    router.get("/test/123/bar", "BASE")

    with pytest.raises(NotFound):
        router.get("/test/foo/aaaa", "BASE")
    with pytest.raises(NotFound):
        router.get("/test/123/aaaa", "BASE")
    with pytest.raises(NotFound):
        router.get("/test/123/aaaa/bbbb", "BASE")


def test_use_route_type_coercion_deeper(handler):
    router = Router()
    router.add("/test/<foo:int>", handler)
    router.add("/test/<foo:int>/bar", handler)
    router.add("/test/<foo:int>/bar/baz", handler)

    router.finalize()

    router.get("/test/123", "BASE")
    router.get("/test/123/bar", "BASE")
    router.get("/test/123/bar/baz", "BASE")

    with pytest.raises(NotFound):
        router.get("/test/foo/aaaa", "BASE")
    with pytest.raises(NotFound):
        router.get("/test/123/aaaa", "BASE")
    with pytest.raises(NotFound):
        router.get("/test/123/aaaa/bbbb", "BASE")
    with pytest.raises(NotFound):
        router.get("/test/123/aaaa/bbbb/cccc", "BASE")
    with pytest.raises(NotFound):
        router.get("/test/foo/bar", "BASE")
    with pytest.raises(NotFound):
        router.get("/test/123/bar/bbbb", "BASE")
    with pytest.raises(NotFound):
        router.get("/test/123/bar/bbbb/cccc", "BASE")


def test_route_correct_coercion():
    def handler1():
        ...

    def handler2():
        ...

    def handler3():
        ...

    def handler4():
        ...

    router = Router()
    router.add("/<test:string>", handler1)
    router.add("/<test:int>", handler2)
    router.add("/<test:uuid>", handler3)
    router.add("/<test:ymd>", handler4)

    router.finalize()

    _, h1, __ = router.get("/foo", "BASE")
    _, h2, __ = router.get("/123", "BASE")
    _, h3, __ = router.get("/726a7d33-4bd5-46a3-a02d-37da7b4b029b", "BASE")
    _, h4, __ = router.get("/2021-03-21", "BASE")

    assert h1 is handler1
    assert h2 is handler2
    assert h3 is handler3
    assert h4 is handler4
