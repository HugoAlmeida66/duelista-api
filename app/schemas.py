"""Contratos JSON e validação das entradas."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

NomeCarta = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
NomeDeck = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Idioma = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
Tipo = Literal["monstro", "magia", "armadilha"]
Conservacao = Literal["nova", "boa", "usada", "danificada"]
Quantidade = Annotated[int, Field(strict=True, ge=1, le=999)]
Texto = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


class Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CartaCriar(Entrada):
    nome: NomeCarta
    tipo: Tipo
    quantidade: Quantidade
    idioma: Idioma = "Português"
    conservacao: Conservacao = "boa"
    observacoes: Texto = ""


class CartaAtualizar(Entrada):
    nome: NomeCarta | None = None
    tipo: Tipo | None = None
    quantidade: Quantidade | None = None
    idioma: Idioma | None = None
    conservacao: Conservacao | None = None
    observacoes: Texto | None = None

    @model_validator(mode="after")
    def validar_patch(self):
        if not self.model_fields_set or any(getattr(self, k) is None for k in self.model_fields_set):
            raise ValueError("Envie ao menos um campo válido, sem valores nulos.")
        return self


class CartaSaida(CartaCriar):
    model_config = ConfigDict(from_attributes=True)
    id: int


class DeckCriar(Entrada):
    nome: NomeDeck
    descricao: Texto = ""


class DeckAtualizar(Entrada):
    nome: NomeDeck | None = None
    descricao: Texto | None = None

    @model_validator(mode="after")
    def validar_patch(self):
        if not self.model_fields_set or any(getattr(self, k) is None for k in self.model_fields_set):
            raise ValueError("Envie ao menos um campo válido, sem valores nulos.")
        return self


class DeckSaida(DeckCriar):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ItemEntrada(Entrada):
    quantidade: Quantidade


class ItemSaida(BaseModel):
    carta: CartaSaida
    quantidade: int


class DeckDetalhe(DeckSaida):
    itens: list[ItemSaida]
    total_cartas: int
