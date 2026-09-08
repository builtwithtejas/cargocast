"""
Universal Schema Base: Transparent Pydantic / Standard-Library Compatibility Layer.
- When 'pydantic' is available, uses native Pydantic v2 BaseModel and Field.
- When 'pydantic' is not installed (e.g. fresh Python 3.14 environments),
  falls back seamlessly to a pure standard-library BaseModel implementation
  supporting typed attributes, defaults, Field specifications, and .model_dump().
"""

try:
    from pydantic import BaseModel as _PydanticBaseModel, Field as _PydanticField
    # Verify pydantic works
    HAS_PYDANTIC = True
    BaseModel = _PydanticBaseModel
    Field = _PydanticField
except ImportError:
    HAS_PYDANTIC = False
    from enum import Enum
    from typing import (
        Any, Dict, List, Optional, Union, get_type_hints, get_origin, get_args
    )

    class FieldInfo:
        def __init__(self, default=..., default_factory=None, description=None, **kwargs):
            self.default = default
            self.default_factory = default_factory
            self.description = description
            self.extra = kwargs

    def Field(default=..., default_factory=None, description=None, **kwargs):
        return FieldInfo(default=default, default_factory=default_factory, description=description, **kwargs)

    class BaseModel:
        def __init__(self, **kwargs):
            # Resolve type annotations across inheritance hierarchy
            hints = {}
            for cls in reversed(self.__class__.__mro__):
                if hasattr(cls, '__annotations__'):
                    hints.update(cls.__annotations__)

            # Assign values
            for name, hint in hints.items():
                if name.startswith('_'):
                    continue

                val = kwargs.get(name, ...)
                if val is ...:
                    # Look for default on class
                    field_def = getattr(self.__class__, name, ...)
                    if isinstance(field_def, FieldInfo):
                        if field_def.default_factory is not None:
                            val = field_def.default_factory()
                        elif field_def.default is not ...:
                            val = field_def.default
                        else:
                            val = None
                    elif field_def is not ...:
                        val = field_def
                    else:
                        val = None

                # Type coercion for nested models and enums
                origin = get_origin(hint)
                args = get_args(hint)

                # Check Optional[X] or Union[X, None]
                if origin is Union and len(args) == 2 and type(None) in args:
                    actual_type = args[0] if args[1] is type(None) else args[1]
                    origin = get_origin(actual_type)
                    args = get_args(actual_type)
                    if origin is None:
                        hint = actual_type

                if val is not None:
                    # List of nested BaseModels
                    if origin is list and args and isinstance(args[0], type) and issubclass(args[0], BaseModel):
                        if isinstance(val, list):
                            val = [args[0](**item) if isinstance(item, dict) else item for item in val]
                    # Dict of nested BaseModels
                    elif origin is dict and len(args) == 2 and isinstance(args[1], type) and issubclass(args[1], BaseModel):
                        if isinstance(val, dict):
                            val = {k: args[1](**v) if isinstance(v, dict) else v for k, v in val.items()}
                    # Direct nested BaseModel
                    elif isinstance(hint, type) and issubclass(hint, BaseModel) and isinstance(val, dict):
                        val = hint(**val)
                    # Enum conversion
                    elif isinstance(hint, type) and issubclass(hint, Enum) and not isinstance(val, Enum):
                        try:
                            val = hint(val)
                        except (ValueError, KeyError):
                            pass

                setattr(self, name, val)

            # Also assign any extra kwargs passed
            for k, v in kwargs.items():
                if k not in hints:
                    setattr(self, k, v)

        def model_dump(self) -> Dict[str, Any]:
            dump = {}
            for k, v in self.__dict__.items():
                if k.startswith('_'):
                    continue
                dump[k] = self._dump_val(v)
            return dump

        @staticmethod
        def _dump_val(val: Any) -> Any:
            if isinstance(val, BaseModel):
                return val.model_dump()
            elif isinstance(val, Enum):
                return val.value
            elif isinstance(val, list):
                return [BaseModel._dump_val(x) for x in val]
            elif isinstance(val, dict):
                return {k: BaseModel._dump_val(v) for k, v in val.items()}
            return val

        def __repr__(self) -> str:
            attrs = ', '.join(f"{k}={v!r}" for k, v in self.__dict__.items() if not k.startswith('_'))
            return f"{self.__class__.__name__}({attrs})"
