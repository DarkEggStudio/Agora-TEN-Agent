from dataclasses import dataclass, fields
import builtins
from typing import TypeVar, Type
from ten import TenEnv

T = TypeVar('T', bound='BaseConfig')


@dataclass
class BaseConfig:
    """
    Base class for implementing configuration. 
    Extra configuration fields can be added in inherited class. 
    """

    @classmethod
    def create(cls: Type[T], ten_env: TenEnv) -> T:
        c = cls()
        c._init(ten_env)
        return c

    def _init(obj, ten_env: TenEnv):
        """
        Get property from ten_env to initialize the dataclass config.    
        """
        for field in fields(obj):
            # TODO: 'is_property_exist' has a bug that can not be used in async extension currently, use it instead of try .. except once fixed
            # if not ten_env.is_property_exist(field.name):
            #     continue
            try:
                ten_env.log_info(f"init field.name: {field.name}")
                match field.type:
                    case builtins.str:
                        val = ten_env.get_property_string(field.name)
                        if val:
                            setattr(obj, field.name, val)
                    case builtins.int:
                        val = ten_env.get_property_int(field.name)
                        setattr(obj, field.name, val)
                    case builtins.bool:
                        val = ten_env.get_property_bool(field.name)
                        setattr(obj, field.name, val)
                    case builtins.float:
                        val = ten_env.get_property_float(field.name)
                        setattr(obj, field.name, val)
                    case _:
                        pass
            except Exception as e:
                ten_env.log_error(f"Error: {e}")
