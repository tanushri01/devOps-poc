from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from typing import List
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from prometheus_client import Counter, Summary, generate_latest, CONTENT_TYPE_LATEST

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://dev:dev@db:5432/itemsdb")

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

REQUEST_TIME = Summary('request_processing_seconds', 'Time spent processing request')
REQUEST_COUNT = Counter('app_requests_total', 'Total HTTP requests')

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)

Base.metadata.create_all(bind=engine)

class ItemIn(BaseModel):
    name: str
    description: str = None

class ItemOut(ItemIn):
    id: int

app = FastAPI(title="Simple Items API")

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/items", response_model=ItemOut)
def create_item(payload: ItemIn):
    db = SessionLocal()
    item = Item(name=payload.name, description=payload.description)
    db.add(item)
    db.commit()
    db.refresh(item)
    db.close()
    return ItemOut(id=item.id, name=item.name, description=item.description)

@app.get("/items", response_model=List[ItemOut])
def list_items():
    db = SessionLocal()
    rows = db.query(Item).all()
    db.close()
    return [ItemOut(id=r.id, name=r.name, description=r.description) for r in rows]

@app.get("/items/{item_id}", response_model=ItemOut)
def get_item(item_id: int):
    db = SessionLocal()
    item = db.query(Item).filter(Item.id == item_id).first()
    db.close()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return ItemOut(id=item.id, name=item.name, description=item.description)

@app.put("/items/{item_id}", response_model=ItemOut)
def update_item(item_id: int, payload: ItemIn):
    db = SessionLocal()
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        db.close()
        raise HTTPException(status_code=404, detail="Item not found")
    item.name = payload.name
    item.description = payload.description
    db.commit()
    db.refresh(item)
    db.close()
    return ItemOut(id=item.id, name=item.name, description=item.description)

@app.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: int):
    db = SessionLocal()
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        db.close()
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
    db.close()
    return None
