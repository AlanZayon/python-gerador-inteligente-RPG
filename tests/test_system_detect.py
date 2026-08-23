from services.system_detect import VALID_PRESETS, detect_system_heuristic


def test_heuristic_detects_gurps():
    assert detect_system_heuristic("GURPS Lite Fourth Edition uses 3d6 and character points") == "gurps"


def test_heuristic_detects_blood_honor():
    text = "Blood and Honor is a samurai tragedy of clan, daimyo, and bushido."
    assert detect_system_heuristic(text) == "blood_honor"
    assert detect_system_heuristic("blood-honor-um-jogo-de-tragedia-samurai.pdf") == "blood_honor"


def test_heuristic_detects_fragged():
    text = "Fragged Empire follows remnant corporations, archon relics, and post-human cultures."
    assert detect_system_heuristic(text) == "fragged"


def test_heuristic_detects_dnd():
    assert detect_system_heuristic("Dungeons and Dragons 5th edition 5e Player's Handbook") == "dnd5e"


def test_new_presets_are_valid():
    assert {"gurps", "blood_honor", "fragged", "dnd5e"} <= VALID_PRESETS
