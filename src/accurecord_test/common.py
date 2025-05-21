from dataclasses import dataclass

import structlog


def get_logger(module_name: str):
    return structlog.get_logger().bind(module=module_name)


@dataclass(frozen=True)
class get_web_logger:
    module_name: str

    def __call__(self):
        return get_logger(self.module_name)
