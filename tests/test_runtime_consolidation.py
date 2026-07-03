import inspect

import main


def test_public_runtime_routes_delegate_to_gateway_service():
    route_expectations = [
        (main.gateway_chat, "execute_chat"),
        (main.chat, "execute_chat"),
        (main.chat_completions, "execute_chat"),
        (main.execute_request, "execute_approval"),
    ]

    for route, gateway_method in route_expectations:
        source = inspect.getsource(route)
        assert gateway_method in source
        assert "graph.invoke" not in source


def test_gateway_service_factory_is_the_route_entrypoint():
    for route in (main.gateway_chat, main.chat, main.chat_completions, main.execute_request):
        source = inspect.getsource(route)
        assert "get_gateway_service()" in source
