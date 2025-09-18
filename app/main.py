from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# ----------------------------
# Database setup
# ----------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")  # Change to MySQL if needed

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ----------------------------
# Database model
# ----------------------------
class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)

Base.metadata.create_all(bind=engine)

# ----------------------------
# Pydantic schemas
# ----------------------------
class ItemIn(BaseModel):
    name: str
    description: Optional[str] = None

class ItemOut(ItemIn):
    id: int

# ----------------------------
# FastAPI app
# ----------------------------
app = FastAPI(title="CRUD API Example")

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------------------
# CRUD Endpoints
# ----------------------------

# Create
@app.post("/items", response_model=ItemOut)
def create_item(item: ItemIn):
    db = next(get_db())
    db_item = Item(name=item.name, description=item.description)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return ItemOut(id=db_item.id, name=db_item.name, description=db_item.description)

# Read all
@app.get("/items", response_model=List[ItemOut])
def read_items():
    db = next(get_db())
    items = db.query(Item).all()
    return [ItemOut(id=i.id, name=i.name, description=i.description) for i in items]

# Read one
@app.get("/items/{item_id}", response_model=ItemOut)
def read_item(item_id: int):
    db = next(get_db())
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return ItemOut(id=item.id, name=item.name, description=item.description)

# Update
@app.put("/items/{item_id}", response_model=ItemOut)
def update_item(item_id: int, item_data: ItemIn):
    db = next(get_db())
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    item.name = item_data.name
    item.description = item_data.description
    db.commit()
    db.refresh(item)
    return ItemOut(id=item.id, name=item.name, description=item.description)

# Delete
@app.delete("/items/{item_id}")
def delete_item(item_id: int):
    db = next(get_db())
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
    return {"detail": "Item deleted successfully"}

# Root endpoint
@app.get("/")
def root():
    return {"message": "CRUD API is running"}
