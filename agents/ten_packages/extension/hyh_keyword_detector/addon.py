#
#
#
from ten import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)
from .detector import KeywordDetector
from .log import logger

@register_addon_as_extension("hyh_keyword_detector")
class KeywordDetectorExtensionAddon(Addon):

    def on_create_instance(self, ten_env: TenEnv, name: str, context) -> None:
        logger.info("KeywordDetectorExtensionAddon on_create_instance")
        ten_env.on_create_instance_done(KeywordDetector(name), context)
