from dataclasses import dataclass, asdict


@dataclass
class Noticia:
    """Noticia original encontrada en una fuente (materia prima para el artículo)."""
    url: str
    fuente: str
    titulo: str
    fecha: str                 # AAAA-MM-DD (publicación, o primer día visto si la fuente no la da)
    resumen: str = ""
    texto: str = ""
    orden: int = 0             # posición en el listado de la fuente (0 = más destacada)

    def a_dict(self) -> dict:
        return asdict(self)


@dataclass
class Precio:
    fuente: str
    region: str
    tipo: str                  # AOVE | Virgen | Lampante | (otros de InfaOliva)
    fecha: str                 # AAAA-MM-DD
    eur_kg: float | None
    nota: str = ""             # p. ej. "Sin cierre de operaciones"
