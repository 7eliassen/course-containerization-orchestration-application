from sqlalchemy.orm import Session
from app.models import Note


def create_note(db: Session, text: str, owner: str) -> Note:
    note = Note(text=text, owner=owner)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def get_notes(db: Session, owner: str | None = None) -> list[Note]:
    query = db.query(Note)
    if owner:
        query = query.filter(Note.owner == owner)
    return query.order_by(Note.created_at.desc()).all()


def get_note_by_id(db: Session, note_id: int) -> Note | None:
    return db.query(Note).filter(Note.id == note_id).first()


def delete_note(db: Session, note_id: int) -> bool:
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        return False
    db.delete(note)
    db.commit()
    return True

