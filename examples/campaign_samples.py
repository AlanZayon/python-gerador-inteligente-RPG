"""High-quality static campaign examples for /example-campaign demo."""

SAMPLES = {
    "mediana": {
        "en": """# The Shattered Crown of Valdris

## Inspired by your book
- Valdris
- Crown of Stars
- The Ashen Gate
- Ironclad Oath
- Thornwall Keep

## Overview
The kingdom of Valdris fractures after the Crown of Stars shatters during a ritual gone wrong. The party must recover three shards before a war of succession consumes the borderlands.

## Starting Hook
At Thornwall Keep, the PCs witness a knight of the Ironclad Oath die while delivering a shard-map — his last words: "The Ashen Gate opens at new moon."

## Session 1: Thornwall Intrigue
**Objectives:** Secure the first shard clue; identify the assassin faction.

**Scene A — The dying knight:** Social encounter; Medicine DC 12 to stabilize long enough for testimony.

**Scene B — Feast hall:** Investigation (Perception DC 14) reveals poisoned wine linked to House Merrow.

**Combat:** 4 thugs + 1 mage (CR 2 equivalent) if PCs confront Merrow agents.

## Session 2: The Ashen Gate
**Objectives:** Navigate the cursed ruin; recover Shard I.

**Puzzle:** Three braziers must be lit in order shown on the map (Investigation DC 13).

**Boss:** Wraith-bound steward (resistant to non-magical weapons unless shard-light is used).

## Session 3: Crown Assembly
**Objectives:** Choose which claimant to support; final confrontation at Valdris throne room.

**Branching endings:** Restore unified crown / install regency / destroy shards to end the curse.

## Important NPCs
- **Seraphine Merrow:** Claimant; charismatic, hides cult ties.
- **Brother Aldric:** Shard scholar; provides lore and healing.

## Rewards
Shard-touched weapons (+1, glow near gates), 800 gp in royal stipends, title "Wardens of Valdris."
""",
        "pt": """# A Coroa Partida de Valdris

## Inspirado no seu livro
- Valdris
- Coroa das Estrelas
- Portão Cinza
- Juramento de Ferro
- Fortaleza Espinhwall

## Visão Geral
O reino de Valdris se fragmenta após a Coroa das Estrelas se partir durante um ritual. O grupo deve recuperar três fragmentos antes que uma guerra de sucessão consuma as fronteiras.

## Gancho Inicial
Em Fortaleza Espinhwall, os PJs testemunham um cavaleiro do Juramento de Ferro morrer enquanto entrega um mapa de fragmentos.

## Sessão 1: Intriga em Espinhwall
Investigação social, combate opcional contra agentes da Casa Merrow, pistas sobre veneno no salão.

## Sessão 2: O Portão Cinza
Ruína amaldiçoada, quebra-cabeça de braseiros, confronto com mordomo espectral.

## Sessão 3: Montagem da Coroa
Escolha de claimants, final no salão do trono de Valdris, múltiplos finais.

## NPCs
Seraphine Merrow, Irmão Aldric.

## Recompensas
Armas tocadas pelo fragmento (+1), 800 PO, título de Guardiões de Valdris.
""",
    },
    "simples": {
        "en": """# The Whispering Cellar

## Overview
A one-shot mystery: villagers vanish near the old mill. The cellar beneath hides a fey bargain gone wrong.

## Session 1
Arrival at Millhaven, talk to miller Hodge, explore cellar, fight 2 sprites and negotiate with bound dryad.

## Session 2
Break the pact stone; optional combat with corrupted fey lord; reward: charm of safe passage.

## NPCs
Hodge (miller), Lirien (dryad).

## Rewards
150 gp, Charm of the Mill (advantage on saves vs charm once/day).
""",
    },
    "complexa": {
        "en": """# Echoes of the Deep Archive

## Overview
Six-session arc: a planar library leaks forbidden lore into a university city. Three factions vie for control; PCs decide which knowledge survives.

## Arc 1 (Sessions 1-2): Matriculation & Missing Curator
## Arc 2 (Sessions 3-4): Vault of Unbound Pages
## Arc 3 (Sessions 5-6): The Index War — three endings

## NPCs
Curator Voss, Archivist Null, Student revolutionary Kira.

## Rewards
Tome-bound spells, faculty titles, or exile depending on ending.
""",
    },
}


def get_sample_campaign(complexity: str, language: str) -> str | None:
    bucket = SAMPLES.get(complexity) or SAMPLES.get("mediana")
    if not bucket:
        return None
    return bucket.get(language) or bucket.get("en")
