import Nafak


# Nafak.py already extracts the page iframe and server-switch embed URLs from
# the TubeAce player markup. Keep this entrypoint separate so source hydration
# can call NafakOnline.py scene-by-url the same way ShrmhaSource.py calls
# ShrmhaOnline.py scene-by-url.
Nafak.main()
