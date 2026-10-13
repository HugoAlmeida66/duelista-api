"""Mapeamento das entidades para tabelas relacionais."""
from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Carta(Base):
    __tablename__ = "cartas"
    __table_args__ = (CheckConstraint("quantidade >= 1"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    chave_nome: Mapped[str] = mapped_column(String(120), unique=True)
    tipo: Mapped[str] = mapped_column(String(10))
    quantidade: Mapped[int]
    idioma: Mapped[str] = mapped_column(String(30))
    conservacao: Mapped[str] = mapped_column(String(30))
    observacoes: Mapped[str] = mapped_column(Text, default="")


class Deck(Base):
    __tablename__ = "decks"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(80))
    chave_nome: Mapped[str] = mapped_column(String(80), unique=True)
    descricao: Mapped[str] = mapped_column(Text, default="")
    itens: Mapped[list["ItemDeck"]] = relationship(
        cascade="all, delete-orphan", back_populates="deck"
    )


class ItemDeck(Base):
    __tablename__ = "itens_deck"
    __table_args__ = (CheckConstraint("quantidade >= 1"),)
    deck_id: Mapped[int] = mapped_column(ForeignKey("decks.id"), primary_key=True)
    carta_id: Mapped[int] = mapped_column(ForeignKey("cartas.id"), primary_key=True)
    quantidade: Mapped[int]
    deck: Mapped[Deck] = relationship(back_populates="itens")
    carta: Mapped[Carta] = relationship()
