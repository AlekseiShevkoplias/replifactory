from datetime import datetime
from sqlalchemy import JSON
import json
from replifactory_server.database import db

class ExperimentModel(db.Model):
    __tablename__ = 'experiments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='inactive')
    parameters = db.Column(db.Text, nullable=False)  # JSON string
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    def __init__(self, name, parameters):
        self.name = name
        self.status = 'inactive'
        self.parameters = json.dumps(parameters) if isinstance(parameters, dict) else parameters
        
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'status': self.status,
            'parameters': json.loads(self.parameters) if isinstance(self.parameters, str) else self.parameters,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class MeasurementData(db.Model):
    __tablename__ = 'measurements'
    id = db.Column(db.Integer, primary_key=True)
    experiment_id = db.Column(db.Integer, db.ForeignKey('experiments.id'), nullable=False)
    vial = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    od = db.Column(db.Float)
    temperature = db.Column(db.Float)
    drug_concentration = db.Column(db.Float)
    growth_rate = db.Column(db.Float)

class DilutionData(db.Model):
    __tablename__ = 'dilutions'
    id = db.Column(db.Integer, primary_key=True)
    experiment_id = db.Column(db.Integer, db.ForeignKey('experiments.id'), nullable=False)
    vial = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    media_volume = db.Column(db.Float)
    drug_volume = db.Column(db.Float)
    target_concentration = db.Column(db.Float)