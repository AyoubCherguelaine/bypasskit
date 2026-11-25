from .session import Session
from .policies import DomainPolicy, PolicyMap
from .solvers import ManualSolver, TurnstileSolver
from .errors import *

def get(url, **kw):
    with Session(**kw) as s:
        return s.fetch(url)