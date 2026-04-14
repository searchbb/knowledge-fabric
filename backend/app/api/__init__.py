"""
API路由模块
"""

from flask import Blueprint

graph_bp = Blueprint('graph', __name__)
simulation_bp = Blueprint('simulation', __name__)
report_bp = Blueprint('report', __name__)
review_bp = Blueprint('review', __name__)
concept_bp = Blueprint('concept', __name__)
theme_bp = Blueprint('theme', __name__)
evolution_bp = Blueprint('evolution', __name__)
registry_bp = Blueprint('registry', __name__)

from . import graph  # noqa: E402, F401
from . import simulation  # noqa: E402, F401
from . import report  # noqa: E402, F401
from .routes import concept_registry  # noqa: E402, F401
from .routes import review_tasks  # noqa: E402, F401
from .routes import themes  # noqa: E402, F401
from .routes import workspace_views  # noqa: E402, F401
from .routes import global_registry  # noqa: E402, F401
from .routes import global_themes  # noqa: E402, F401
from .routes import evolution_log  # noqa: E402, F401
from .routes import review_queue  # noqa: E402, F401
from .routes import registry_export  # noqa: E402, F401
from .routes import workspace_overview  # noqa: E402, F401
from .routes import cross_relations  # noqa: E402, F401
