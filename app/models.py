from flask_sqlalchemy import SQLAlchemy
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from .extensions import db

class User(db.Model):
    __tablename__ = 'users'
    __table_args__ = {'extend_existing': True}  # <--- FIXUL PENTRU EROAREA TA
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    # Role-based access
    is_admin = db.Column(db.Boolean, default=False)
    
    grids = db.relationship('Grid', backref='owner', lazy=True)
    active_grid_id = db.Column(db.BigInteger, nullable=True)
    
class Grid(db.Model):
    __tablename__ = 'grids'
    __table_args__ = {'extend_existing': True}  # <--- FIXUL PENTRU EROAREA TA

    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    
    name = db.Column(db.String(50), default='New Grid')
    slot_number = db.Column(db.SmallInteger, nullable=False)
    center_point = db.Column(Geometry('POINT', srid=4326), nullable=False)
    dimension = db.Column(db.Integer, default=100)
    cell_size_meters = db.Column(db.Integer, default=50)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
class UnlockedCell(db.Model):
    __tablename__ = 'unlocked_cells'
    __table_args__ = {'extend_existing': True}  # <--- FIXUL PENTRU EROAREA TA

    grid_id = db.Column(db.BigInteger, db.ForeignKey('grids.id'), primary_key=True)
    row_index = db.Column(db.Integer, primary_key=True)
    col_index = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(255))
    unlocked_at = db.Column(db.DateTime, default=datetime.utcnow)