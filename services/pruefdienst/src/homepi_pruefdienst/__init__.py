"""HomePI-Prüfdienst: liest DFBnet und spielt in das Artefakt ein.

Kein Artefakt im Gateway, sondern ein eigener Container: er fährt minutenlang
einen echten Browser, und die synchrone Playwright-API lässt sich aus einer
laufenden Event-Loop ohnehin nicht aufrufen.
"""

__version__ = "0.1.0"
