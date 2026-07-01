"""RMM consent-aware endpoint agent.

Design contract (do not weaken):
  * The agent is VISIBLE: it shows a persistent tray icon with connection
    status, and raises an OS notification when a remote session starts.
  * The agent does NOT log keystrokes. It uses pynput *Controllers* to inject
    the admin's input during an active session; it never installs a global
    *Listener* that would capture the local user's own keystrokes.
  * Screen capture and input injection only run while a session is ACTIVE,
    and every session is announced to the user and logged on the server.

These properties are what separate a legitimate RMM agent from a RAT. They are
intentional and load-bearing.
"""

__version__ = "0.2.0"
