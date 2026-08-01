"""Enterprise Feature Store.

Turns the deterministic financial signals produced by the ratio/health engines
into versioned, ML-ready feature vectors. Each feature carries its ``value``
``feature_name``, ``description``, ``version``, ``generated_time``, ``source``
and ``confidence`` — the exact contract the phase brief specifies.

Public surface
--------------
* :mod:`feature_registry` - the versioned catalogue of feature definitions
* :mod:`feature_builder` - computes :class:`Feature` values for a context
* :mod:`feature_pipeline` - high-level entrypoints (engine input / statement)
* :mod:`feature_serializer` - (de)serialisation to/from persistence & API
* :mod:`feature_store` - versioned persistence of feature vectors

The layer is intentionally read-only with respect to the scoring engines: it
consumes their outputs and never mutates them.
"""

from .feature_pipeline import (  # noqa: F401
    build_from_document_fields,
    build_from_engine_input,
    build_from_mapping,
    build_from_statement,
)
from .feature_registry import FEATURE_SET_VERSION, get_registry  # noqa: F401
